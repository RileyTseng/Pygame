import pygame
import random
import math
from collections import deque

# ---------------------- 配置 ----------------------
CELL_SIZE = 25
WIDTH = 900
HEIGHT = 600
ROWS = HEIGHT // CELL_SIZE
COLS = WIDTH // CELL_SIZE
EXTRA_PATHS = 350
FPS = 60

# ---------------------- 初始化 ----------------------
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Maze Game - 3 Levels")
clock = pygame.time.Clock()
# Pick a font that supports Chinese characters; prefer common Windows fonts then fall back to default.
font_candidates = [
    "Microsoft JhengHei", "Microsoft JhengHei UI", "SimHei", "SimSun",
    "Arial Unicode MS", "NotoSansCJK-Regular"
]
font_path = None
for name in font_candidates:
    match = pygame.font.match_font(name)
    if match:
        font_path = match
        break

if font_path:
    # Use a specific TTF path to ensure Chinese glyphs render
    font = pygame.font.Font(font_path, 48)
else:
    # Fallback to the default system font
    font = pygame.font.SysFont(None, 48)

# ---------------------- 顏色 ----------------------
BG_COLOR = (0, 26, 51)
WALL_COLOR = (255, 255, 255)
PLAYER_COLOR = (255, 255, 0)
EXIT_COLOR = (0, 255, 0)
HIDDEN_COLOR = (0, 0, 0)  # ★遮蔽黑色
TRAP_COLOR = (200, 0, 200)  # 新增：傳送陷阱顏色（紫色）
MONSTER_COLOR = (255, 105, 180)  # 粉紅色：半夜放閃的情侶（定點）
PUPPY_COLOR = (255, 200, 200)  # 心碎小狗顏色（淺粉）
START_COLOR = (255, 165, 0)  # 起點方塊（橘色），可穿透
QUIZ_MONSTER_COLOR = (255, 0, 0)  # 紅色：中央常識題庫怪物（移動、可穿透）

# ---------------------- 遊戲狀態 ----------------------
maze = []
player = {'x': 1, 'y': 1}
exit_pos = {'x': ROWS - 2, 'y': COLS - 2}
glow_time = 0
show_victory = False
traps = set()  # 存放 (r,c) 的傳送陷阱位置
monster = None  # store monster info or None. monster = {
#   'cells': {(r1,c1),(r2,c2)}, 'triggered': False
# }
reveal_until = 0  # pygame.time.get_ticks() ms until which fog is removed
puppy = None  # heartbroken puppy dict or None: {'pos':(r,c), 'activated':False, 'delivered':False}
path_history = deque(maxlen=32)  # keep recent player positions for following behavior
exit_attempts = 0  # attempts to step on exit while puppy active and undelivered
show_message = False
message_text = ""
message_suppressed = False  # if True, the last_message_text was closed by the player (space) and shouldn't re-show
last_message_text = None

# ---------------------- 中央常識題庫怪物（移動怪） ----------------------
quiz_monsters = []  # list of {'pos':(r,c)}
quiz_move_interval = 500  # ms between moves (0.5s)
quiz_last_move = 0
quiz_active = False
quiz_current = None  # {'index': idx, 'question': q, 'answer': a, 'input': ''}
quiz_input_focused = False
quiz_caret_last = 0

# 題庫（問題 -> 答案）
QUESTIONS = [
    ("中央大學後門那條路叫甚麼?", "中央路"),
    ("中央松果餐廳的飲料店叫甚麼?", "Comebuy"),
    ("中央裡面的全家打幾折", "85折"),
    ("中央裡面的7-11打幾折", "9折"),
    ("中央iHouse開到幾點?", "21:00"),
]

level = 1
visible_map = None  # 第二關用：走過的格子

# ---------------------- 迷宮生成 ----------------------
def generate_perfect_maze():
    maze = [[1]*COLS for _ in range(ROWS)]

    def carve(x, y):
        maze[x][y] = 0
        dirs = [(1,0), (-1,0), (0,1), (0,-1)]
        random.shuffle(dirs)
        for dx, dy in dirs:
            nx, ny = x + dx*2, y + dy*2
            if 0 < nx < ROWS-1 and 0 < ny < COLS-1 and maze[nx][ny] == 1:
                maze[x+dx][y+dy] = 0
                carve(nx, ny)
    carve(1, 1)
    return maze

def add_extra_paths(maze, amount=EXTRA_PATHS):
    for _ in range(amount):
        r = random.randint(0, ROWS-1)
        c = random.randint(0, COLS-1)
        maze[r][c] = 0

def is_reachable(maze, startX, startY, endX, endY):
    visited = [[False]*COLS for _ in range(ROWS)]
    queue = deque([(startX, startY)])
    visited[startX][startY] = True
    while queue:
        x, y = queue.popleft()
        if x == endX and y == endY:
            return True
        for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
            nx, ny = x+dx, y+dy
            if 0<=nx<ROWS and 0<=ny<COLS and not visited[nx][ny] and maze[nx][ny]==0:
                visited[nx][ny] = True
                queue.append((nx, ny))
    return False

def ensure_exit_reachable(maze):
    global exit_pos
    exit_pos = {'x': ROWS-2, 'y': COLS-2}
    maze[exit_pos['x']][exit_pos['y']] = 0
    if not is_reachable(maze, 1,1, exit_pos['x'], exit_pos['y']):
        cx, cy = exit_pos['x'], exit_pos['y']
        while not is_reachable(maze, 1,1, cx, cy):
            dirs = [(-1,0),(0,-1),(1,0),(0,1)]
            random.shuffle(dirs)
            for dx, dy in dirs:
                nx, ny = cx+dx, cy+dy
                if 0<nx<ROWS-1 and 0<ny<COLS-1:
                    maze[nx][ny] = 0
                    if is_reachable(maze,1,1,nx,ny):
                        cx, cy = nx, ny
                        break

# ---------------------- 實體 / 物件生成 helpers ----------------------
def spawn_traps():
    global traps
    traps.clear()
    available = [(r, c) for r in range(ROWS) for c in range(COLS)
                 if maze[r][c] == 0 and not (r == player['x'] and c == player['y'])
                 and not (r == exit_pos['x'] and c == exit_pos['y'])]
    trap_count = random.randint(3, 7)
    if available:
        trap_count = min(trap_count, len(available))
        chosen = random.sample(available, trap_count)
        for pos in chosen:
            traps.add(pos)

def spawn_quiz_monsters():
    global quiz_monsters, quiz_last_move
    quiz_monsters.clear()
    qm_count = random.randint(5, 6)
    available_qm = [(r, c) for r in range(ROWS) for c in range(COLS)
                    if maze[r][c] == 0 and (r, c) != (player['x'], player['y'])
                    and (r, c) != (exit_pos['x'], exit_pos['y'])
                    and (r, c) not in traps]
    if monster is not None:
        for cell in monster['cells']:
            if cell in available_qm:
                available_qm.remove(cell)
    # and avoid puppy location if present
    if puppy is not None and puppy.get('pos') in available_qm:
        available_qm.remove(puppy.get('pos'))

    if available_qm:
        qm_count = min(qm_count, len(available_qm))
        chosen_qm = random.sample(available_qm, qm_count)
        for pos in chosen_qm:
            quiz_monsters.append({'pos': pos, 'question': None, 'answer': None})
    quiz_last_move = pygame.time.get_ticks()

def spawn_static_monster():
    global monster, reveal_until
    monster = None
    reveal_until = 0
    if level in (2, 3) and random.randint(0, 1) == 1:
        attempts = 200
        placed = False
        for _ in range(attempts):
            r = random.randint(1, ROWS-2)
            c = random.randint(1, COLS-2)
            if maze[r][c] != 0:
                continue
            dirs = [(1,0), (-1,0), (0,1), (0,-1)]
            random.shuffle(dirs)
            for dr, dc in dirs:
                r2, c2 = r+dr, c+dc
                if 0 <= r2 < ROWS and 0 <= c2 < COLS and maze[r2][c2] == 0:
                    if (r, c) == (player['x'], player['y']) or (r2, c2) == (player['x'], player['y']):
                        continue
                    if (r, c) == (exit_pos['x'], exit_pos['y']) or (r2, c2) == (exit_pos['x'], exit_pos['y']):
                        continue
                    if (r, c) in traps or (r2, c2) in traps:
                        continue

                    maze[r][c] = 1
                    maze[r2][c2] = 1
                    reachable = is_reachable(maze, 1, 1, exit_pos['x'], exit_pos['y'])
                    maze[r][c] = 0
                    maze[r2][c2] = 0
                    if reachable:
                        monster = {'cells': {(r, c), (r2, c2)}, 'triggered': False}
                        placed = True
                        break
            if placed:
                break

def spawn_puppy():
    global puppy, path_history, exit_attempts, show_message, message_text
    puppy = None
    path_history.clear()
    path_history.append((player['x'], player['y']))
    exit_attempts = 0
    show_message = False
    message_text = ""
    if level == 3:
        attempts = 200
        for _ in range(attempts):
            r = random.randint(1, ROWS-2)
            c = random.randint(1, COLS-2)
            if maze[r][c] != 0:
                continue
            if (r, c) == (player['x'], player['y']) or (r, c) == (exit_pos['x'], exit_pos['y']):
                continue
            if (r, c) in traps:
                continue
            if monster is not None and (r, c) in monster['cells']:
                continue

            maze[r][c] = 1
            ok = is_reachable(maze, 1, 1, exit_pos['x'], exit_pos['y'])
            maze[r][c] = 0
            if ok:
                puppy = {'pos': (r, c), 'activated': False, 'delivered': False}
                break

# ---------------------- 更新與繪圖 helpers ----------------------

def draw_cell_entities(r, c, rect, in_current_view):
    """Draw any entities on a cell (traps, static 2-cell monster, puppy, moving quiz monsters).
       This keeps drawing logic centralized and easier to read."""
    # exit
    if r == exit_pos['x'] and c == exit_pos['y']:
        pygame.draw.rect(screen, EXIT_COLOR, rect)

    # start (level 3) small orange inner square
    if level == 3 and (r, c) == (1, 1):
        inner = (rect[0]+CELL_SIZE//8, rect[1]+CELL_SIZE//8, CELL_SIZE*3//4, CELL_SIZE*3//4)
        pygame.draw.rect(screen, START_COLOR, inner)

    # traps (draw small square)
    if (r, c) in traps and in_current_view:
        inner = (rect[0]+CELL_SIZE//6, rect[1]+CELL_SIZE//6, CELL_SIZE*2//3, CELL_SIZE*2//3)
        pygame.draw.rect(screen, TRAP_COLOR, inner)

    # static two-cell monster (full square)
    if monster is not None and (r, c) in monster['cells'] and in_current_view:
        pygame.draw.rect(screen, MONSTER_COLOR, rect)

    # puppy
    if puppy is not None and (r, c) == puppy['pos'] and in_current_view:
        pygame.draw.rect(screen, PUPPY_COLOR, rect)

    # moving quiz monsters (small inner square)
    for qm in quiz_monsters:
        if (r, c) == qm['pos'] and in_current_view:
            inner = (rect[0]+CELL_SIZE//6, rect[1]+CELL_SIZE//6, CELL_SIZE*2//3, CELL_SIZE*2//3)
            pygame.draw.rect(screen, QUIZ_MONSTER_COLOR, inner)

def generate_maze():
    global maze, player, show_victory
    global level, visible_map
    global monster, reveal_until
    global puppy, path_history, exit_attempts, show_message, message_text, message_suppressed, last_message_text

    maze = generate_perfect_maze()
    add_extra_paths(maze)
    ensure_exit_reachable(maze)
    player = {'x':1, 'y':1}
    show_victory = False
    # reset any message suppression when generating a new maze (allow messages again)
    message_suppressed = False
    last_message_text = None
    # start path history with starting position
    path_history.append((player['x'], player['y']))

    # spawn traps and moving quiz monsters
    spawn_traps()

    spawn_quiz_monsters()

    # 在第二、三關可能放置 0~1 個「雙格怪物」；怪物佔兩個相鄰地面格，且不能放在起點、出口或陷阱位置
    # reset reveal state and monster reference for new maze
    monster = None
    reveal_until = 0
    spawn_static_monster()

    # 關卡視野設定
    if level == 1:
        visible_map = None
    elif level == 2:
        visible_map = [[False]*COLS for _ in range(ROWS)]
        visible_map[player['x']][player['y']] = True
    elif level == 3:
        visible_map = None
    spawn_puppy()

# ---------------------- 遊戲邏輯 ----------------------
def move_player(dx, dy):
    global show_victory, level, visible_map
    global reveal_until
    global puppy, path_history, exit_attempts, show_message, message_text, message_suppressed, last_message_text
    global quiz_monsters, quiz_active, quiz_current

    nx, ny = player['x'] + dx, player['y'] + dy
    # 不能移動到牆或怪物占格
    blocked_by_monster = False
    if monster is not None:
        if (nx, ny) in monster['cells']:
            blocked_by_monster = True

    blocked_by_puppy = False
    if puppy is not None and not puppy.get('activated', False):
        if (nx, ny) == puppy.get('pos'):
            blocked_by_puppy = True

    if 0 <= nx < ROWS and 0 <= ny < COLS and maze[nx][ny] == 0 and not blocked_by_monster and not blocked_by_puppy:
        player['x'], player['y'] = nx, ny

        # ★ 第2關：只記錄“走過”的格子
        if level == 2:
            visible_map[nx][ny] = True

        # append path history for puppy following
        path_history.append((player['x'], player['y']))

        # 過關判定：如果有被啟動但未被送走的心碎小狗，則不能過關
        if nx == exit_pos['x'] and ny == exit_pos['y']:
            # if puppy active and not delivered, block victory and show message
            if level == 3 and puppy is not None and puppy.get('activated', False) and not puppy.get('delivered', False):
                exit_attempts += 1
                if exit_attempts > 3:
                    new_msg = "你怎麼可以不送小狗回家?"
                else:
                    new_msg = "你是不是忘了要送誰回家"
                # only show if user hasn't suppressed this exact message
                if message_suppressed and last_message_text == new_msg:
                    # do not re-show
                    pass
                else:
                    message_text = new_msg
                    show_message = True
                    # reset suppression when showing a new/different message
                    message_suppressed = False
                    last_message_text = None
                print(new_msg)
            else:
                show_victory = True
                pygame.time.set_timer(pygame.USEREVENT, 2000, loops=1)

                if level < 3:
                    level += 1
                    generate_maze_for_next_level()

        # ★ 處理傳送陷阱：如果踩到 trap，則立即傳送至地圖上另一個隨機非牆位置（排除出口與其他陷阱），並且移除該陷阱
        if (nx, ny) in traps:
            # remove the trap so it cannot be retriggered
            traps.discard((nx, ny))

            # 找所有可傳送的位置：非牆且不是其他陷阱、不是出口，也不能是玩家當前位置（避免原地傳送）
            curr_pos = (nx, ny)
            destinations = [(r, c) for r in range(ROWS) for c in range(COLS)
                            if maze[r][c] == 0 and (r, c) not in traps
                            and not (r == exit_pos['x'] and c == exit_pos['y'])
                            and not (r, c) == curr_pos]
            # exclude monster cells
            if monster is not None:
                destinations = [d for d in destinations if d not in monster['cells']]
            if destinations:
                dest_r, dest_c = random.choice(destinations)
                # 明確設定整數格座標以確保角色仍在格子中心
                player['x'], player['y'] = int(dest_r), int(dest_c)

                # 如果是第二關，也要把傳送到的新格子標記為已探索
                if level == 2 and visible_map is not None:
                    visible_map[int(dest_r)][int(dest_c)] = True
            else:
                # 沒有可傳送的合法位置：保留在原地，但已移除觸發陷阱
                pass

        # ★ 檢查是否接近（撞上）怪物的範圍（距離 ≤ 1）以觸發視野消失效果，如果怪物尚未被觸發
        if monster is not None and not monster.get('triggered', False):
            # player's current position
            px, py = player['x'], player['y']
            triggered = False
            for (mr, mc) in monster['cells']:
                # 僅在四向相鄰（不包含對角）才視為觸發
                if abs(mr - px) + abs(mc - py) == 1:
                    triggered = True
                    break
            if triggered:
                monster['triggered'] = True
                # 取消視野遮蔽：把 reveal_until 設為四秒以後
                reveal_until = pygame.time.get_ticks() + 4000

        # 心碎小狗：啟動 / 跟隨 / 送回家
        if level == 3 and puppy is not None:
            # activation when puppy is inside view (5x5 centered on player)
            if not puppy.get('activated', False):
                if abs(puppy['pos'][0] - player['x']) <= 2 and abs(puppy['pos'][1] - player['y']) <= 2:
                    puppy['activated'] = True
                    new_msg = "終於有人要送我回家了嗎!!!!"
                    if message_suppressed and last_message_text == new_msg:
                        # suppressed by player previously -> don't re-show
                        pass
                    else:
                        message_text = new_msg
                        show_message = True
                        message_suppressed = False
                        last_message_text = None
                    print(new_msg)
                    # set initial follow position
                    if len(path_history) >= 3:
                        puppy['pos'] = path_history[-3]
            else:
                # once activated and not delivered, puppy follows two tiles behind
                if not puppy.get('delivered', False) and len(path_history) >= 3:
                    puppy['pos'] = path_history[-3]

        # 若玩家回到起點並且 puppy 已啟動未送達，視為送回家 -> 消失並顯示訊息
        if level == 3 and puppy is not None and puppy.get('activated', False) and not puppy.get('delivered', False):
            start_pos = (1, 1)
            if (player['x'], player['y']) == start_pos:
                puppy['delivered'] = True
                puppy = None
                new_msg = "謝謝你帶我回家"
                if not (message_suppressed and last_message_text == new_msg):
                    message_text = new_msg
                    show_message = True
                    message_suppressed = False
                    last_message_text = None
                print(new_msg)
                exit_attempts = 0

        # ---- 碰到 quiz monster by player movement (未觸發前重疊即觸發) ----
        if not quiz_active:
            for i, qm in enumerate(quiz_monsters):
                if qm.get('pos') == (player['x'], player['y']):
                    # choose a question for this monster when triggered
                    if not qm.get('question'):
                        q, a = random.choice(QUESTIONS)
                        qm['question'], qm['answer'] = q, a
                    else:
                        q, a = qm['question'], qm['answer']
                    quiz_active = True
                    quiz_current = {'index': i, 'question': q, 'answer': a, 'input': ""}
                    quiz_input_focused = True
                    # enable IME / text input mode so TEXTINPUT events provide composed characters (Chinese)
                    try:
                        pygame.key.start_text_input()
                    except Exception:
                        pass
                    print(q)
                    break

# ---------------------- 視野繪圖 ----------------------
def draw_limited_view():
    radius = 2
    px, py = player['x'], player['y']

    for r in range(ROWS):
        for c in range(COLS):
            rect = (c*CELL_SIZE, r*CELL_SIZE, CELL_SIZE, CELL_SIZE)
            in_current_view = abs(r - px) <= radius and abs(c - py) <= radius

            if level == 2:
                # ★顯示條件：走過 or 目前 5×5
                if not visible_map[r][c] and not in_current_view:
                    pygame.draw.rect(screen, HIDDEN_COLOR, rect)
                    continue

            if level == 3:
                if not in_current_view:
                    pygame.draw.rect(screen, HIDDEN_COLOR, rect)
                    continue

            # 正常繪製
            if maze[r][c] == 1:
                pygame.draw.rect(screen, WALL_COLOR, rect)
            else:
                pygame.draw.rect(screen, BG_COLOR, rect)

            # draw entities on visible cell
            draw_cell_entities(r, c, rect, True)

# ---------------------- 繪圖 ----------------------
def draw_exit_glow():
    global glow_time
    glow_time += 0.15
    px = exit_pos['y']*CELL_SIZE + CELL_SIZE//2
    py = exit_pos['x']*CELL_SIZE + CELL_SIZE//2
    glow = 12 + math.sin(glow_time)*6
    for i in range(6):
        pygame.draw.circle(screen, EXIT_COLOR, (px,py), int(glow*(i/6)), 2)

def draw_game():
    global quiz_input_focused, quiz_caret_last
    screen.fill(BG_COLOR)
    current_time = pygame.time.get_ticks()
    reveal_active = current_time < reveal_until

    if level == 1 or reveal_active:
        # 完整視野
        for r in range(ROWS):
            for c in range(COLS):
                if maze[r][c] == 1:
                    pygame.draw.rect(screen, WALL_COLOR, (c*CELL_SIZE, r*CELL_SIZE, CELL_SIZE, CELL_SIZE))
                else:
                    pygame.draw.rect(screen, BG_COLOR, (c*CELL_SIZE, r*CELL_SIZE, CELL_SIZE, CELL_SIZE))
                    # draw entities on full/reveal view
                    draw_cell_entities(r, c, (c*CELL_SIZE, r*CELL_SIZE, CELL_SIZE, CELL_SIZE), True)
    else:
        draw_limited_view()

    draw_exit_glow()

    # 玩家
    pygame.draw.rect(screen, PLAYER_COLOR, (player['y']*CELL_SIZE, player['x']*CELL_SIZE, CELL_SIZE, CELL_SIZE))

    if show_victory:
        text = font.render("Victory!", True, (255,255,0))
        screen.blit(text, (WIDTH//2-100, HEIGHT//2-24))

    if show_message and message_text:
        text = font.render(message_text, True, (255,255,255))
        screen.blit(text, (20, HEIGHT - 60))

    # quiz overlay for question/answer (centered white box)
    if quiz_active and quiz_current is not None:
        box_w, box_h = WIDTH * 2 // 3, HEIGHT // 3
        box_x = (WIDTH - box_w) // 2
        box_y = (HEIGHT - box_h) // 2
        # white background
        pygame.draw.rect(screen, (255,255,255), (box_x, box_y, box_w, box_h))
        # question text (top part)
        q_text = font.render(quiz_current['question'], True, (0,0,0))
        screen.blit(q_text, (box_x + 20, box_y + 20))
        # input box bottom area
        input_box = (box_x + 20, box_y + box_h - 70, box_w - 40, 50)
        pygame.draw.rect(screen, (230,230,230), input_box)
        input_text = font.render(quiz_current.get('input', ''), True, (0,0,0))
        screen.blit(input_text, (input_box[0] + 10, input_box[1] + 10))
        # caret blinking when focused
        if quiz_input_focused:
            now = pygame.time.get_ticks()
            if now - quiz_caret_last >= 500:
                quiz_caret_last = now
            # blink on/off every 500ms
            if (now // 500) % 2 == 0:
                caret_x = input_box[0] + 10 + input_text.get_width()
                caret_y1 = input_box[1] + 8
                caret_y2 = input_box[1] + 8 + input_text.get_height()
                pygame.draw.line(screen, (0,0,0), (caret_x, caret_y1), (caret_x, caret_y2), 2)

    pygame.display.flip()

# ---------------------- 下一關迷宮生成 ----------------------
def generate_maze_for_next_level():
    global maze, visible_map, show_victory
    global monster, reveal_until
    global puppy, path_history, exit_attempts, show_message, message_text, message_suppressed, last_message_text

    maze = generate_perfect_maze()
    add_extra_paths(maze)
    ensure_exit_reachable(maze)
    show_victory = False

    spawn_traps()

    spawn_quiz_monsters()

    if level == 2:
        visible_map = [[False]*COLS for _ in range(ROWS)]
        visible_map[player['x']][player['y']] = True
    elif level == 3:
        visible_map = None

    spawn_static_monster()
    spawn_puppy()

# ---------------------- 主程式 ----------------------
generate_maze()

running = True
while running:
    clock.tick(FPS)
    for event in pygame.event.get():
        if event.type==pygame.QUIT:
            running = False
        elif event.type==pygame.KEYDOWN:
            # If quiz overlay is active, capture text input for it and skip normal key handling
            if quiz_active:
                if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                    # submit answer
                    if quiz_current is not None:
                        user_ans = quiz_current['input'].strip()
                        # case-insensitive compare for ascii answers
                        correct = user_ans.lower() == quiz_current['answer'].strip().lower()
                        idx = quiz_current['index']
                        if correct:
                            if 0 <= idx < len(quiz_monsters):
                                # remove the quiz monster from the map on success
                                del quiz_monsters[idx]
                            quiz_active = False
                            quiz_current = None
                            # stop text input and unfocus
                            try:
                                pygame.key.stop_text_input()
                            except Exception:
                                pass
                            quiz_input_focused = False
                        else:
                            # wrong -> clear the stored question for that monster so it will re-pick next time
                            if 0 <= idx < len(quiz_monsters):
                                quiz_monsters[idx]['question'] = None
                                quiz_monsters[idx]['answer'] = None
                            # send player back to start
                            player['x'], player['y'] = 1, 1
                            path_history.append((player['x'], player['y']))
                            quiz_active = False
                            quiz_current = None
                            try:
                                pygame.key.stop_text_input()
                            except Exception:
                                pass
                            quiz_input_focused = False
                elif event.key == pygame.K_BACKSPACE:
                    if quiz_current is not None:
                        quiz_current['input'] = quiz_current['input'][:-1]
                else:
                    if quiz_current is not None and event.unicode and quiz_input_focused:
                        # limit input length
                        if len(quiz_current['input']) < 120:
                            quiz_current['input'] += event.unicode
                # don't process other keys while in quiz
                continue

            # close any message overlay first (space to close)
            if show_message and event.key == pygame.K_SPACE:
                # suppress re-showing the same message until it changes
                last_message_text = message_text
                message_suppressed = True
                show_message = False
                message_text = ""
                continue
            # click/focus handled in MOUSEBUTTONDOWN; if the player presses TAB to toggle focus we support it
            if quiz_active and event.key == pygame.K_TAB:
                quiz_input_focused = not quiz_input_focused
                continue

            if show_victory:
                if event.key == pygame.K_SPACE:
                    generate_maze()
            else:
                if event.key==pygame.K_UP:
                    move_player(-1,0)
                elif event.key==pygame.K_DOWN:
                    move_player(1,0)
                elif event.key==pygame.K_LEFT:
                    move_player(0,-1)
                elif event.key==pygame.K_RIGHT:
                    move_player(0,1)
                elif event.key in [pygame.K_r, pygame.K_SPACE]:
                    generate_maze()
        elif event.type == pygame.TEXTINPUT:
            # IME / unicode text events for quiz input
            if quiz_active and quiz_input_focused and quiz_current is not None:
                if len(quiz_current['input']) < 120:
                    quiz_current['input'] += event.text
        elif event.type==pygame.USEREVENT:
            generate_maze()
        elif event.type == pygame.MOUSEBUTTONDOWN:
            # if quiz overlay active, clicking inside the input box gives it focus
            if quiz_active and quiz_current is not None:
                mouse_x, mouse_y = event.pos
                box_w, box_h = WIDTH * 2 // 3, HEIGHT // 3
                box_x = (WIDTH - box_w) // 2
                box_y = (HEIGHT - box_h) // 2
                input_box = (box_x + 20, box_y + box_h - 70, box_w - 40, 50)
                ix, iy, iw, ih = input_box
                if ix <= mouse_x <= ix + iw and iy <= mouse_y <= iy + ih:
                    quiz_input_focused = True
                else:
                    quiz_input_focused = False

    # update moving quiz monsters every 0.5s (if no quiz active)
    now = pygame.time.get_ticks()
    if not quiz_active and quiz_monsters and now - quiz_last_move >= quiz_move_interval:
        for qm in quiz_monsters:
            # try a random direction; if invalid keep position
            dirs = [(1,0), (-1,0), (0,1), (0,-1)]
            random.shuffle(dirs)
            for dr, dc in dirs:
                nr, nc = qm['pos'][0] + dr, qm['pos'][1] + dc
                # cannot move out of bounds, into wall, or into start (1,1)
                if 0 <= nr < ROWS and 0 <= nc < COLS and maze[nr][nc] == 0 and (nr, nc) != (1,1):
                    # do not move into player's exact position if that would immediately trigger
                    qm['pos'] = (nr, nc)
                    break
            # if a quiz monster moved onto the player, trigger the quiz (if not cleared)
            if qm.get('pos') == (player['x'], player['y']) and not quiz_active:
                # if this monster hasn't chosen a question yet, give it one now
                if not qm.get('question'):
                    q, a = random.choice(QUESTIONS)
                    qm['question'], qm['answer'] = q, a
                else:
                    q, a = qm['question'], qm['answer']
                quiz_active = True
                # find index
                idx = quiz_monsters.index(qm)
                quiz_current = {'index': idx, 'question': q, 'answer': a, 'input': ""}
                quiz_input_focused = True
                try:
                    pygame.key.start_text_input()
                except Exception:
                    pass
                print(q)
                quiz_input_focused = True
                try:
                    pygame.key.start_text_input()
                except Exception:
                    pass
                print(q)
        quiz_last_move = now

    draw_game()

pygame.quit()
