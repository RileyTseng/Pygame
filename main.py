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

# ---------------------- 遊戲狀態 ----------------------
maze = []
player = {'x': 1, 'y': 1}
exit_pos = {'x': ROWS - 2, 'y': COLS - 2}
glow_time = 0
show_victory = False

# ★新增：關卡與視野資料
level = 1
visible_map = None

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
        currentX, currentY = exit_pos['x'], exit_pos['y']
        while not is_reachable(maze, 1,1, currentX, currentY):
            dirs = [(-1,0),(0,-1),(1,0),(0,1)]
            random.shuffle(dirs)
            for dx, dy in dirs:
                nx, ny = currentX+dx, currentY+dy
                if 0<nx<ROWS-1 and 0<ny<COLS-1:
                    maze[nx][ny] = 0
                    if is_reachable(maze,1,1,nx,ny):
                        currentX, currentY = nx, ny
                        break

def generate_maze():
    global maze, player, show_victory
    global level, visible_map

    def _generate(reset_player=True):
        global maze, player, show_victory, visible_map
        maze = generate_perfect_maze()
        add_extra_paths(maze)
        ensure_exit_reachable(maze)
        if reset_player:
            player = {'x':1, 'y':1}
        show_victory = False
        # ★ 視野設定（依關卡）
        if level == 2:
            visible_map = [[False]*COLS for _ in range(ROWS)]
        elif level == 3:
            visible_map = None
    # 預設第一次呼叫重設玩家
    _generate(reset_player=True)

# ---------------------- 遊戲邏輯 ----------------------
def move_player(dx, dy):
    global show_victory, level

    nx, ny = player['x'] + dx, player['y'] + dy
    if 0 <= nx < ROWS and 0 <= ny < COLS and maze[nx][ny] == 0:
        player['x'], player['y'] = nx, ny

        if nx == exit_pos['x'] and ny == exit_pos['y']:
            show_victory = True
            # 只觸發一次 USEREVENT，避免遊戲一直被重置
            pygame.time.set_timer(pygame.USEREVENT, 2000, loops=1)

            # ★ 過關自動升級到下一關
            if level < 3:
                level += 1
                # 升級時不重設玩家位置
                generate_maze_for_next_level()

# ---------------------- 視野繪圖 ----------------------
def draw_limited_view():
    global visible_map

    radius = 2
    px, py = player['x'], player['y']

    for r in range(px - radius, px + radius + 1):
        for c in range(py - radius, py + radius + 1):
            if 0 <= r < ROWS and 0 <= c < COLS:

                # 第2關：視野會被記錄
                if level == 2 and visible_map is not None:
                    visible_map[r][c] = True

                # 第2關：沒看過的格子不畫
                if level == 2:
                    if visible_map is None or not visible_map[r][c]:
                        continue

                # 第3關：只畫當前 5×5
                if level == 3:
                    if abs(r - px) > radius or abs(c - py) > radius:
                        continue

                rect = (c*CELL_SIZE, r*CELL_SIZE, CELL_SIZE, CELL_SIZE)
                if maze[r][c] == 1:
                    pygame.draw.rect(screen, WALL_COLOR, rect)
                else:
                    pygame.draw.rect(screen, BG_COLOR, rect)

                if r == exit_pos['x'] and c == exit_pos['y']:
                    pygame.draw.rect(screen, EXIT_COLOR, rect)


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

    # ★依關卡決定視野
    if level == 1:
        # 第1關：完整視野
        for r in range(ROWS):
            for c in range(COLS):
                if maze[r][c]==1:
                    pygame.draw.rect(screen, WALL_COLOR, (c*CELL_SIZE, r*CELL_SIZE, CELL_SIZE, CELL_SIZE))
    else:
        # 第2、3關：小視野
        draw_limited_view()

    draw_exit_glow()

    # 玩家
    pygame.draw.rect(screen, PLAYER_COLOR, (player['y']*CELL_SIZE, player['x']*CELL_SIZE, CELL_SIZE, CELL_SIZE))

    # 勝利提示
    if show_victory:
        text = font.render("Victory!", True, (255,255,0))
        screen.blit(text, (WIDTH//2-100, HEIGHT//2-24))

    pygame.display.flip()


# ---------------------- 主程式 ----------------------
def generate_maze_for_next_level():
    # 只重設迷宮和視野，不重設玩家位置
    global maze, show_victory, visible_map, player
    maze = generate_perfect_maze()
    add_extra_paths(maze)
    ensure_exit_reachable(maze)
    show_victory = False
    if level == 2:
        # 保留玩家目前位置周圍的視野
        radius = 2
        if visible_map is None:
            visible_map = [[False]*COLS for _ in range(ROWS)]
        for r in range(player['x'] - radius, player['x'] + radius + 1):
            for c in range(player['y'] - radius, player['y'] + radius + 1):
                if 0 <= r < ROWS and 0 <= c < COLS:
                    visible_map[r][c] = True
    elif level == 3:
        visible_map = None

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


