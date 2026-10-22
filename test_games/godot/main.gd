extends Node2D

var player := Vector2(20, 56)
var enemies: Array[Vector2] = []
var items: Array[Vector2] = [Vector2(28, 92)]
var hp: int = 100
var tick: int = 0
var auth_required: bool = false
var speed: int = 4
var attack_range: int = 14
var max_steps: int = 600
var walls: Array[Rect2] = [Rect2(72, 28, 9, 53)]
var bridge: String = ""
var report_path: String = ""
var run_id: String = ""
var elapsed: float = 0.0
var render_sync: bool = false
var publishing: bool = false
var pending_action: String = ""
const KEY_ACTIONS: Dictionary = {KEY_ESCAPE: "authenticate", KEY_Z: "attack", KEY_X: "use_item", KEY_SPACE: "jump", KEY_LEFT: "move_left", KEY_RIGHT: "move_right", KEY_UP: "move_up", KEY_DOWN: "move_down"}

func _ready() -> void:
    var config: Dictionary = {}
    if FileAccess.file_exists("res://arena.json"):
        var decoded: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://arena.json"))
        if decoded is Dictionary:
            config = decoded
    for arg in OS.get_cmdline_user_args():
        if arg == "--uga-render-sync":
            render_sync = true
        if arg.begins_with("--uga-seed="):
            config["seed"] = int(arg.trim_prefix("--uga-seed="))
        if arg.begins_with("--uga-bridge="):
            bridge = arg.trim_prefix("--uga-bridge=")
        if arg.begins_with("--uga-report="):
            report_path = arg.trim_prefix("--uga-report=")
        if arg.begins_with("--uga-run-id="):
            run_id = arg.trim_prefix("--uga-run-id=")
    setup(config)
    if not bridge.is_empty():
        if render_sync:
            await RenderingServer.frame_post_draw
        publish_state()

func setup(config: Dictionary) -> void:
    player = Vector2(20, 56)
    items = [Vector2(28, 92)]
    hp = 100
    tick = 0
    auth_required = false
    speed = int(config.get("speed", 4))
    attack_range = int(config.get("attack_range", 14))
    max_steps = int(config.get("max_steps", 600))
    walls.clear()
    if config.get("obstacles", true):
        walls.append(Rect2(72, 28, 9, 53))
    var rng := RandomNumberGenerator.new()
    rng.seed = int(config.get("seed", 7))
    var positions: Array[Vector2] = []
    for x in [108, 124, 144]:
        for y in [20, 40, 64, 88, 104]:
            positions.append(Vector2(x, y))
    enemies.clear()
    for index in range(clampi(int(config.get("enemy_count", 3)), 1, 8)):
        var selected: int = rng.randi_range(0, positions.size() - 1)
        enemies.append(positions[selected])
        positions.remove_at(selected)
    queue_redraw()

func won() -> bool:
    return enemies.is_empty() and hp > 0

func done() -> bool:
    return won() or hp <= 0 or tick >= max_steps

func step(action: String) -> bool:
    if done() or auth_required:
        return false
    tick += 1
    var effect: bool = false
    var offsets: Dictionary = {"move_left": Vector2.LEFT, "move_right": Vector2.RIGHT, "move_up": Vector2.UP, "move_down": Vector2.DOWN}
    if offsets.has(action):
        var candidate: Vector2 = player + offsets[action] * speed
        var blocked: bool = candidate.x < 4 or candidate.x > 156 or candidate.y < 16 or candidate.y > 108
        for wall in walls:
            if wall.grow(2).has_point(candidate):
                blocked = true
        if not blocked:
            player = candidate
            effect = true
    elif action == "attack":
        for index in range(enemies.size()):
            if enemies[index].distance_to(player) <= attack_range:
                enemies.remove_at(index)
                effect = true
                break
    elif action == "use_item":
        for index in range(items.size()):
            if items[index].distance_to(player) <= 10:
                items.remove_at(index)
                hp = mini(100, hp + 30)
                effect = true
                break
    elif action == "jump":
        effect = true
    if tick % 5 == 0 and action != "jump":
        for enemy in enemies:
            if enemy.distance_to(player) < 11:
                hp = maxi(0, hp - 6)
    queue_redraw()
    return effect

func snapshot() -> Dictionary:
    var enemy_positions: Array = []
    var item_positions: Array = []
    for enemy in enemies:
        enemy_positions.append([enemy.x, enemy.y])
    for item in items:
        item_positions.append([item.x, item.y])
    var obstacles: Array = []
    for wall in walls:
        obstacles.append([wall.position.x, wall.position.y, wall.end.x - 1, wall.end.y - 1])
    return {"run_id": run_id, "tick": tick, "player": [player.x, player.y], "hp": hp, "enemies": enemy_positions, "items": item_positions, "obstacles": obstacles, "won": won(), "done": done(), "auth_required": auth_required}

func write_json(path: String, value: Dictionary) -> void:
    var handle := FileAccess.open(path + ".tmp", FileAccess.WRITE)
    if handle == null:
        push_error("Cannot write UGA state: " + path)
        return
    handle.store_string(JSON.stringify(value))
    handle.close()
    var err: Error = DirAccess.rename_absolute(path + ".tmp", path)
    if err != OK:
        push_error("Cannot publish UGA state: " + str(err))

func publish_state() -> void:
    write_json(bridge.path_join("state.json"), snapshot())

func _process(_delta: float) -> void:
    if bridge.is_empty() or publishing:
        return
    var action_path: String = bridge.path_join("action.json")
    if FileAccess.file_exists(action_path) and FileAccess.get_file_as_string(action_path).length() < 65536:
        var message: Variant = JSON.parse_string(FileAccess.get_file_as_string(action_path))
        if message is Dictionary and message.get("run_id") == run_id and int(message.get("frame", -1)) == tick:
            var action: String = str(message.get("action", "wait"))
            if render_sync and done() and action == "finish":
                if not report_path.is_empty():
                    write_json(report_path, snapshot())
                get_tree().quit(0 if won() else 2)
                return
            publishing = true
            step(action)
            if render_sync:
                await RenderingServer.frame_post_draw
            publish_state()
            publishing = false
            if (done() or auth_required) and not render_sync:
                if not report_path.is_empty():
                    write_json(report_path, snapshot())
                get_tree().quit(0 if won() else 2)

func _unhandled_input(event: InputEvent) -> void:
    # Keep a press made between 0.1 s samples so a short tap is applied exactly once.
    var key := event as InputEventKey
    if not bridge.is_empty() or key == null or not key.pressed or key.echo:
        return
    var action: String = KEY_ACTIONS.get(key.physical_keycode, "")
    if action == "authenticate" or pending_action.is_empty():
        pending_action = action

func held_action() -> String:
    for key in KEY_ACTIONS:
        if Input.is_physical_key_pressed(key):
            return KEY_ACTIONS[key]
    return "wait"

func _physics_process(delta: float) -> void:
    if not bridge.is_empty():
        return
    elapsed += delta
    if elapsed < 0.1:
        return
    elapsed = 0.0
    var action: String = held_action() if pending_action.is_empty() else pending_action
    pending_action = ""
    if action == "authenticate":
        auth_required = true
        action = "wait"
    step(action)

func _draw() -> void:
    draw_rect(Rect2(0, 0, 160, 112), Color8(18, 22, 35))
    draw_rect(Rect2(0, 0, 4, 4), Color8(10, 220, 230))
    draw_rect(Rect2(4, 0, 4, 4), Color8(255, 180, 0) if auth_required else Color8(20, 200, 80))
    if won():
        draw_rect(Rect2(8, 0, 4, 4), Color8(180, 100, 255))
    draw_rect(Rect2(10, 6, hp, 3), Color8(240, 60, 60))
    for wall in walls:
        draw_rect(wall, Color8(110, 115, 135))
    for item in items:
        draw_rect(Rect2(item - Vector2(2, 2), Vector2(5, 5)), Color8(80, 220, 130))
    for enemy in enemies:
        draw_rect(Rect2(enemy - Vector2(2, 2), Vector2(5, 5)), Color8(240, 70, 90))
    draw_rect(Rect2(player - Vector2(2, 2), Vector2(5, 5)), Color8(70, 160, 250))
