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
font = pygame.font.SysFont(None, 48)

# ---------------------- 顏色 ----------------------
BG_COLOR = (0, 26, 51)
WALL_COLOR = (255, 255, 255)
PLAYER_COLOR = (255, 255, 0)
EXIT_COLOR = (0, 255, 0)
HIDDEN_COLOR = (0, 0, 0)  # ★遮蔽黑色
TRAP_COLOR = (200, 0, 200)  # 新增：傳送陷阱顏色（紫色）

# ---------------------- 遊戲狀態 ----------------------
maze = []
player = {'x': 1, 'y': 1}
exit_pos = {'x': ROWS - 2, 'y': COLS - 2}
glow_time = 0
show_victory = False
traps = set()  # 存放 (r,c) 的傳送陷阱位置

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

def generate_maze():
    global maze, player, show_victory
    global level, visible_map

    maze = generate_perfect_maze()
    add_extra_paths(maze)
    ensure_exit_reachable(maze)
    player = {'x':1, 'y':1}
    show_victory = False

    # ★ 在每張迷宮上隨機放置 3~7 個傳送陷阱，放在地面 (maze == 0) 上，且不能放在玩家起點或出口
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

    # 關卡視野設定
    if level == 1:
        visible_map = None
    elif level == 2:
        visible_map = [[False]*COLS for _ in range(ROWS)]
        visible_map[player['x']][player['y']] = True
    elif level == 3:
        visible_map = None

# ---------------------- 遊戲邏輯 ----------------------
def move_player(dx, dy):
    global show_victory, level, visible_map

    nx, ny = player['x'] + dx, player['y'] + dy
    if 0 <= nx < ROWS and 0 <= ny < COLS and maze[nx][ny] == 0:
        player['x'], player['y'] = nx, ny

        # ★ 第2關：只記錄“走過”的格子
        if level == 2:
            visible_map[nx][ny] = True

        # 過關
        if nx == exit_pos['x'] and ny == exit_pos['y']:
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

            if r == exit_pos['x'] and c == exit_pos['y']:
                pygame.draw.rect(screen, EXIT_COLOR, rect)
            # 畫陷阱（若該格是地面且目前可見）
            if (r, c) in traps:
                # 畫一個小方塊代表陷阱
                inner = (rect[0]+CELL_SIZE//6, rect[1]+CELL_SIZE//6, CELL_SIZE*2//3, CELL_SIZE*2//3)
                pygame.draw.rect(screen, TRAP_COLOR, inner)

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
    screen.fill(BG_COLOR)

    if level == 1:
        # 完整視野
        for r in range(ROWS):
            for c in range(COLS):
                if maze[r][c] == 1:
                    pygame.draw.rect(screen, WALL_COLOR, (c*CELL_SIZE, r*CELL_SIZE, CELL_SIZE, CELL_SIZE))
                else:
                    pygame.draw.rect(screen, BG_COLOR, (c*CELL_SIZE, r*CELL_SIZE, CELL_SIZE, CELL_SIZE))
                    if (r, c) in traps:
                        inner = (c*CELL_SIZE + CELL_SIZE//6, r*CELL_SIZE + CELL_SIZE//6, CELL_SIZE*2//3, CELL_SIZE*2//3)
                        pygame.draw.rect(screen, TRAP_COLOR, inner)
    else:
        draw_limited_view()

    draw_exit_glow()

    # 玩家
    pygame.draw.rect(screen, PLAYER_COLOR, (player['y']*CELL_SIZE, player['x']*CELL_SIZE, CELL_SIZE, CELL_SIZE))

    if show_victory:
        text = font.render("Victory!", True, (255,255,0))
        screen.blit(text, (WIDTH//2-100, HEIGHT//2-24))

    pygame.display.flip()

# ---------------------- 下一關迷宮生成 ----------------------
def generate_maze_for_next_level():
    global maze, visible_map, show_victory

    maze = generate_perfect_maze()
    add_extra_paths(maze)
    ensure_exit_reachable(maze)
    show_victory = False

    # 下一關同樣要放陷阱（3~7 個）
    traps.clear()
    available = [(r, c) for r in range(ROWS) for c in range(COLS)
                 if maze[r][c] == 0 and not (r == player['x'] and c == player['y'])
                 and not (r == exit_pos['x'] and c == exit_pos['y'])]
    trap_count = random.randint(3, 7)
    if available:
        trap_count = min(trap_count, len(available))
        for pos in random.sample(available, trap_count):
            traps.add(pos)

    if level == 2:
        visible_map = [[False]*COLS for _ in range(ROWS)]
        visible_map[player['x']][player['y']] = True
    elif level == 3:
        visible_map = None

# ---------------------- 主程式 ----------------------
generate_maze()

running = True
while running:
    clock.tick(FPS)
    for event in pygame.event.get():
        if event.type==pygame.QUIT:
            running = False
        elif event.type==pygame.KEYDOWN:
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
        elif event.type==pygame.USEREVENT:
            generate_maze()

    draw_game()

pygame.quit()
