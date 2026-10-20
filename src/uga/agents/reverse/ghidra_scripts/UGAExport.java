// Original UGA script. Executed only inside an explicitly approved Ghidra analysis.
// @category UGA
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import com.google.gson.Gson;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class UGAExport extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) throw new IllegalArgumentException("Expected output JSON path");
        List<Map<String, Object>> functions = new ArrayList<>();
        FunctionIterator iterator = currentProgram.getFunctionManager().getFunctions(true);
        while (iterator.hasNext() && !monitor.isCancelled()) {
            Function function = iterator.next();
            Map<String, Object> entry = new LinkedHashMap<>();
            entry.put("name", function.getName());
            entry.put("address", function.getEntryPoint().toString());
            List<String> calls = new ArrayList<>();
            for (Function called : function.getCalledFunctions(monitor)) {
                calls.add(called.getEntryPoint().toString());
            }
            entry.put("calls", calls);
            functions.add(entry);
        }
        if (monitor.isCancelled()) throw new IllegalStateException("Analysis cancelled");
        Map<String, Object> report = new LinkedHashMap<>();
        report.put("program", currentProgram.getName());
        report.put("functions", functions);
        report.put("source", "Ghidra function manager; not a claim of complete recovery");
        Files.write(Paths.get(args[0]), new Gson().toJson(report).getBytes(StandardCharsets.UTF_8));
    }
}
