import json
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from uga.core.errors import AuthorizationRequired, CapabilityUnavailable, UGAError
from uga.integrations.process import run_tool


def _grant(approved, authorized, trusted_input):
    if not approved or not authorized:
        raise AuthorizationRequired(
            "Analyzer execution and target analysis must both be authorized"
        )
    if not trusted_input:
        raise AuthorizationRequired(
            "Untrusted inputs require an external OS sandbox; a child process is not a security sandbox"
        )


class JadxAdapter:
    """Official JADX CLI; JVM classpath form supports Windows without a shell."""

    def __init__(
        self,
        executable: Path | None = None,
        *,
        java: Path | None = None,
        installation: Path | None = None,
    ):
        if java and installation:
            self.command = [
                str(java.resolve()),
                "-Xmx1g",
                "-cp",
                str(installation.resolve() / "lib" / "*"),
                "jadx.cli.JadxCLI",
            ]
        else:
            found = str(executable) if executable else shutil.which("jadx")
            if not found:
                raise CapabilityUnavailable("JADX/64-bit Java >=11 are not configured")
            self.command = [str(Path(found).resolve())]

    def analyze(
        self,
        sample: Path,
        output: Path,
        *,
        approved=False,
        authorized=False,
        trusted_input=False,
        heartbeat=None,
    ):
        _grant(approved, authorized, trusted_input)
        if not sample.is_file() or sample.is_symlink():
            raise ValueError("regular sample file required")
        if output.exists():
            raise FileExistsError(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        result = run_tool(
            [
                *self.command,
                "--threads-count",
                "1",
                "-d",
                str(output.resolve()),
                str(sample.resolve()),
            ],
            output.parent,
            approved=approved,
            timeout_s=120,
            max_rss_mb=2048,
            driver=heartbeat,
        )
        sources = list((output / "sources").rglob("*.java"))
        if not sources:
            raise UGAError("JADX completed without Java sources")
        return {
            "decompiled": True,
            "java_files": len(sources),
            "output": str(output),
            "log": result.output,
            "tool_resources": result.resources,
            "elapsed_s": result.elapsed_s,
        }


class GhidraAdapter:
    def __init__(self, headless: Path | None = None):
        found = str(headless) if headless else shutil.which("analyzeHeadless")
        if not found:
            raise CapabilityUnavailable(
                "Ghidra analyzeHeadless and a compatible JDK are not configured"
            )
        self.executable = Path(found).resolve()

    def analyze(
        self,
        sample: Path,
        output: Path,
        *,
        approved=False,
        authorized=False,
        trusted_input=False,
        heartbeat=None,
    ):
        _grant(approved, authorized, trusted_input)
        if not sample.is_file() or sample.is_symlink():
            raise ValueError("regular sample file required")
        if output.exists():
            raise FileExistsError(output)
        output.mkdir(parents=True)
        script = Path(__file__).parent / "ghidra_scripts"
        report = output.resolve() / "functions.json"
        # Ghidra rejects project paths containing dot-prefixed elements such as .uga.
        # Its temporary project is separate from the caller's retained evidence.
        with tempfile.TemporaryDirectory(prefix="uga-ghidra-") as temporary:
            result = run_tool(
                [
                    str(self.executable),
                    str(Path(temporary).resolve()),
                    "uga-" + uuid4().hex,
                    "-import",
                    str(sample.resolve()),
                    "-scriptPath",
                    str(script.resolve()),
                    "-postScript",
                    "UGAExport.java",
                    str(report),
                    "-analysisTimeoutPerFile",
                    "90",
                    "-max-cpu",
                    "1",
                    "-deleteProject",
                ],
                output,
                approved=approved,
                timeout_s=180,
                max_rss_mb=4096,
                driver=heartbeat,
            )
        if not report.exists():
            raise UGAError("Ghidra did not produce function evidence")
        if report.stat().st_size > 16_000_000:
            raise UGAError("Ghidra function evidence exceeds 16 MB")
        data = json.loads(report.read_text(encoding="utf-8"))
        if not isinstance(data.get("functions"), list):
            raise UGAError("invalid Ghidra export")
        return {
            "analyzed": True,
            "evidence": data,
            "log": result.output,
            "tool_resources": result.resources,
            "elapsed_s": result.elapsed_s,
        }


class REAAdapter:
    """Injected MCP transport. Discover schemas before invoking an explicitly selected tool.

    No server is installed, launched or connected implicitly. Evidence is retained raw;
    unavailable/partial analysis must not be converted into invented game mechanics.
    """

    upstream = "https://github.com/morluto/rea"
    package = "rea-agents@6.7.0"

    def __init__(self, transport=None):
        if transport is None:
            raise CapabilityUnavailable("Configure an approved REA MCP transport first")
        self.transport = transport

    def tools(self):
        tools = self.transport.list_tools()
        if not all(
            isinstance(t.get("name"), str) and isinstance(t.get("inputSchema"), dict) for t in tools
        ):
            raise UGAError("REA discovery returned invalid tool contracts")
        return tools

    def invoke(self, name: str, arguments: dict, *, authorized=False):
        if not authorized:
            raise AuthorizationRequired("REA analysis scope must be authorized")
        if name not in {t["name"] for t in self.tools()}:
            raise ValueError("tool was not discovered from this REA server")
        result = self.transport.call_tool(name, arguments)
        if result.get("isError"):
            raise UGAError("REA tool reported an error")
        return {
            "provider": "REA",
            "tool": name,
            "raw_evidence": result,
            "mechanics_verified": False,
        }


class AsyncREAAdapter(REAAdapter):
    """Same evidence contract for an explicitly connected asynchronous MCP transport."""

    async def tools(self):
        tools = await self.transport.list_tools()
        if not all(
            isinstance(tool.get("name"), str) and isinstance(tool.get("inputSchema"), dict)
            for tool in tools
        ):
            raise UGAError("REA discovery returned invalid tool contracts")
        return tools

    async def invoke(self, name: str, arguments: dict, *, authorized=False):
        if not authorized:
            raise AuthorizationRequired("REA analysis scope must be authorized")
        if name not in {tool["name"] for tool in await self.tools()}:
            raise ValueError("tool was not discovered from this REA server")
        result = await self.transport.call_tool(name, arguments)
        if result.get("isError"):
            raise UGAError("REA tool reported an error")
        return {
            "provider": "REA",
            "tool": name,
            "raw_evidence": result,
            "mechanics_verified": False,
        }
