extends SceneTree

const Arena = preload("res://main.gd")
var failures: Array[String] = []

func check(condition: bool, message: String) -> void:
    if not condition:
        failures.append(message)

func _initialize() -> void:
    call_deferred("run_checks")

func run_checks() -> void:
    var arena := Arena.new()
    root.add_child(arena)
    arena.set_physics_process(false)
    arena.set_process(false)
    arena.setup({"seed": 7, "enemy_count": 1})
    check(arena.step("move_right"), "movement failed")
    check(arena.player == Vector2(24, 56), "wrong movement")
    arena.player = Vector2(68, 56)
    check(not arena.step("move_right"), "wall collision failed")
    arena.player = Vector2(28, 92)
    arena.hp = 40
    check(arena.step("use_item") and arena.hp == 70, "healing item failed")
    arena.auth_required = true
    var before: Vector2 = arena.player
    check(not arena.step("move_right") and arena.player == before, "authentication pause failed")
    arena.auth_required = false
    arena.enemies = [Vector2(32, 92)]
    check(arena.step("attack") and arena.won(), "combat/goal failed")
    var report_path: String = ""
    var run_id: String = ""
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--uga-report="):
            report_path = arg.trim_prefix("--uga-report=")
        if arg.begins_with("--uga-run-id="):
            run_id = arg.trim_prefix("--uga-run-id=")
    if not report_path.is_empty():
        arena.write_json(report_path, {"run_id": run_id, "checks": 6, "passed": failures.is_empty(), "failures": failures})
    if not failures.is_empty():
        printerr(JSON.stringify(failures))
    arena.queue_free()
    quit(0 if failures.is_empty() else 1)
