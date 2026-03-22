#!/usr/bin/env python3
"""
五子棋 AI - v25 (Alpha-Beta 搜索升级 + 智能候选排序)
v25 改进 (2026-03-22):
- 实现 minimax + alpha-beta 剪枝搜索（depth=4）
- 新增 get_ordered_candidates()：威胁等级优先排序，剪枝效率大幅提升
- 新增 find_winning_move()：成五必杀检测
- 新增 find_block_four()：四连防守检测
- find_best_move() 整合：必杀→必防→四连防守→Alpha-Beta搜索
- 保留原有评估函数，节点超限保护稳定运行
"""

import sys
import random

BOARD_SIZE = 15
EMPTY = '.'
BLACK = 'X'
WHITE = 'O'

# 中心区域位置定义（按优先级排序）
CENTER_ZONE = {
    (7, 7),   # H8 - 天元（中心）
    (6, 6), (6, 8), (8, 6), (8, 8),  # G7, I7, G9, I9
    (6, 7), (7, 6), (7, 8), (8, 7),  # H7, G8, I8, H9
    (5, 7), (7, 5), (7, 9), (9, 7),  # H6, G8, I8, H10 (扩展中心)
    (5, 6), (5, 8), (6, 5), (6, 9), (8, 5), (8, 9), (9, 6), (9, 8),  # 更外圈
    (5, 5), (5, 9), (9, 5), (9, 9),  # 角落扩展
}

# 位置权重矩阵（中心权重高，角落权重低）
POSITION_WEIGHTS = [[0] * BOARD_SIZE for _ in range(BOARD_SIZE)]
for r in range(BOARD_SIZE):
    for c in range(BOARD_SIZE):
        # 计算到中心的距离
        dist = abs(r - 7) + abs(c - 7)
        # 距离越近权重越高，边缘权重衰减
        POSITION_WEIGHTS[r][c] = max(0, 50 - dist * 4)


class GomokuAI:
    def __init__(self, board_str=None):
        if board_str:
            self.board = self.parse_board(board_str)
        else:
            self.board = [[EMPTY for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        self.tt = {}           # 转置表
        self._nodes = 0        # 节点计数器（防超时）
        self._node_limit = 8000  # 节点上限
    
    def parse_board(self, board_str):
        # 初始化空棋盘
        board = [[EMPTY for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        
        lines = board_str.strip().split('\n')
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith('A ') or 'A B C D' in stripped:
                continue
            
            # 解析行号（如 "8 . . . . . . . X"）
            parts = stripped.split()
            if not parts:
                continue
            
            # 第一部分是行号（1-15 或 A-O）
            row_idx = None
            first = parts[0].upper()
            # 尝试数字解析
            try:
                row_num = int(parts[0])
                row_idx = row_num - 1  # 转为0索引
            except (ValueError, IndexError):
                # 尝试字母解析 A=1, B=2, ..., O=15
                if len(first) == 1 and 'A' <= first <= 'O':
                    row_idx = ord(first) - ord('A')
                else:
                    # 没有有效行号，跳过
                    continue
            
            if row_idx < 0 or row_idx >= BOARD_SIZE:
                continue
            
            # 提取棋盘数据（从第二部分开始）
            row_data = parts[1:] if len(parts) > 1 else []
            
            for col_idx, ch in enumerate(row_data):
                if col_idx >= BOARD_SIZE:
                    break
                if ch in ['.', '·']:
                    board[row_idx][col_idx] = EMPTY
                elif ch in ['X', '●']:
                    board[row_idx][col_idx] = BLACK
                elif ch in ['O', '○']:
                    board[row_idx][col_idx] = WHITE
        
        return board
    
    def get_connection_score(self, row, col, player):
        """计算连接性评分 - 评估落子后能形成的连接价值"""
        if self.board[row][col] != EMPTY:
            return 0
        
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        total_score = 0
        
        for dr, dc in directions:
            # 统计顺方向
            fwd = 0
            fwd_r, fwd_c = row + dr, col + dc
            fwd_empty = False
            while 0 <= fwd_r < BOARD_SIZE and 0 <= fwd_c < BOARD_SIZE:
                if self.board[fwd_r][fwd_c] == player:
                    fwd += 1
                elif self.board[fwd_r][fwd_c] == EMPTY:
                    fwd_empty = True
                    break
                else:
                    break
                fwd_r += dr
                fwd_c += dc
            
            # 统计逆方向
            bwd = 0
            bwd_r, bwd_c = row - dr, col - dc
            bwd_empty = False
            while 0 <= bwd_r < BOARD_SIZE and 0 <= bwd_c < BOARD_SIZE:
                if self.board[bwd_r][bwd_c] == player:
                    bwd += 1
                elif self.board[bwd_r][bwd_c] == EMPTY:
                    bwd_empty = True
                    break
                else:
                    break
                bwd_r -= dr
                bwd_c -= dc
            
            chain_len = fwd + bwd + 1  # 落子后的总链长
            
            # 连接性评分公式
            if chain_len >= 5:
                score = 10000  # 成五
            elif chain_len == 4:
                if fwd_empty and bwd_empty:
                    score = 2000  # 活四
                elif fwd_empty or bwd_empty:
                    score = 800   # 冲四
                else:
                    score = 100   # 死四
            elif chain_len == 3:
                if fwd_empty and bwd_empty:
                    score = 300   # 活三
                elif fwd_empty or bwd_empty:
                    score = 80    # 眠三
                else:
                    score = 20
            elif chain_len == 2:
                if fwd_empty and bwd_empty:
                    score = 50    # 活二
                elif fwd_empty or bwd_empty:
                    score = 10    # 眠二
                else:
                    score = 2
            else:
                score = 1
            
            total_score += score
        
        return total_score
    
    def find_defense(self, player):
        """找到防守对手的位置，优先返回威胁最大的堵截点
        修复：遍历所有空位，检查对手落子后的威胁等级
        """
        candidates = []
        center = BOARD_SIZE // 2
        
        # 遍历每个空位，检查对手在此落子后是否形成威胁
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if self.board[r][c] != EMPTY:
                    continue
                
                # 检查对手在这个位置落子后的威胁等级
                threat = self.get_threat_level(r, c, player)
                
                # 只关心3连及以上威胁（>=75分）
                if threat >= 75:
                    dist = abs(r - center) + abs(c - center)
                    
                    # 活三(>=90)给最高优先级，眠三(>=80)次之
                    if threat >= 90:  # 活三 - 必须防守
                        score = threat * 15
                    elif threat >= 80:  # 眠三
                        score = threat * 12
                    else:  # 3连（死三）
                        score = threat * 10
                    
                    candidates.append((r, c, score, dist))
        
        if not candidates:
            return None
        
        # 排序: 优先按score降序（威胁等级高优先），同分则距离中心近优先
        candidates.sort(key=lambda x: (-x[2], x[3]))
        return candidates[0][0], candidates[0][1]
    
    def _verify_defense(self, row, col, player, dr, dc):
        """验证在(row,col)落子是否能有效阻断对手
        检查对手在该位置或附近是否还能形成威胁
        如果dr, dc为None，则检查所有方向
        """
        opponent = WHITE if player == BLACK else BLACK
        
        if dr is None or dc is None:
            # 检查所有4个方向 - 对手在这些方向是否还有威胁
            for dr_check, dc_check in [(0,1), (1,0), (1,1), (1,-1)]:
                # 检查对手在这个方向上是否还能形成威胁
                if self._check_opponent_threat(row, col, opponent, dr_check, dc_check):
                    # 对手仍能形成威胁，防守不完全有效
                    continue
            # 如果所有方向对手都不能形成威胁，则防守有效
            return True
        else:
            return not self._check_opponent_threat(row, col, opponent, dr, dc)
    
    def _check_opponent_threat(self, row, col, player, dr, dc):
        """检查对手在指定方向上是否还能形成威胁（>=75）"""
        # 统计该方向上对手的连子数
        fwd = 0
        fwd_r, fwd_c = row + dr, col + dc
        while 0 <= fwd_r < BOARD_SIZE and 0 <= fwd_c < BOARD_SIZE:
            if self.board[fwd_r][fwd_c] == player:
                fwd += 1
            elif self.board[fwd_r][fwd_c] == EMPTY:
                break
            else:
                break
            fwd_r += dr
            fwd_c += dc
        
        bwd = 0
        bwd_r, bwd_c = row - dr, col - dc
        while 0 <= bwd_r < BOARD_SIZE and 0 <= bwd_c < BOARD_SIZE:
            if self.board[bwd_r][bwd_c] == player:
                bwd += 1
            elif self.board[bwd_r][bwd_c] == EMPTY:
                break
            else:
                break
            bwd_r -= dr
            bwd_c -= dc
        
        total = fwd + bwd
        
        # 检查两端是否为空
        fwd_empty = (0 <= fwd_r < BOARD_SIZE and 0 <= fwd_c < BOARD_SIZE and 
                    self.board[fwd_r][fwd_c] == EMPTY)
        bwd_empty = (0 <= bwd_r < BOARD_SIZE and 0 <= bwd_c < BOARD_SIZE and 
                    self.board[bwd_r][bwd_c] == EMPTY)
        
        # 如果有3连且两端有空位，对手仍有威胁
        if total >= 3:
            if total >= 4:
                return True  # 4连及以上，必防
            if total == 3:
                if fwd_empty or bwd_empty:
                    return True  # 活三，仍有威胁
        
        return False
        
        if not candidates:
            return None
        
        # 排序: 优先按score降序
        candidates.sort(key=lambda x: (-x[2], x[3]))
        return candidates[0][0], candidates[0][1]
    
    def estimate_follow_threat(self, row, col, player, dr, dc):
        """预判在(row,col)落子后，对手在同方向能否形成更大威胁"""
        opponent = WHITE if player == BLACK else BLACK
        max_threat = 0
        
        # 检查这个位置落子后，对手能否在两端扩展
        # 前端
        fr, fc = row + dr, col + dc
        if 0 <= fr < BOARD_SIZE and 0 <= fc < BOARD_SIZE and self.board[fr][fc] == EMPTY:
            threat = self.get_threat_level(fr, fc, opponent)
            max_threat = max(max_threat, threat)
        
        # 后端
        br, bc = row - dr, col - dc
        if 0 <= br < BOARD_SIZE and 0 <= bc < BOARD_SIZE and self.board[br][bc] == EMPTY:
            threat = self.get_threat_level(br, bc, opponent)
            max_threat = max(max_threat, threat)
        
        return max_threat
    
    def find_defense_4plus(self, player):
        """专门查找对手4连及以上威胁的位置 - 重写版本"""
        center = BOARD_SIZE // 2
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        
        all_defense_options = []
        
        # 遍历每个位置作为起点
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if self.board[r][c] != player:
                    continue
                for dr, dc in directions:
                    # 向前找连续的同色棋子
                    fwd_stones = []
                    nr, nc = r + dr, c + dc
                    while 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and self.board[nr][nc] == player:
                        fwd_stones.append((nr, nc))
                        nr += dr
                        nc += dc
                    
                    # 向后找连续的同色棋子
                    bwd_stones = []
                    nr, nc = r - dr, c - dc
                    while 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and self.board[nr][nc] == player:
                        bwd_stones.append((nr, nc))
                        nr -= dr
                        nc -= dc
                    
                    total = len(fwd_stones) + len(bwd_stones) + 1  # +1是自己
                    
                    if total >= 4:
                        # 前端防守点
                        if fwd_stones:
                            fr, fc = fwd_stones[-1]
                            nr, nc = fr + dr, fc + dc
                            if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and self.board[nr][nc] == EMPTY:
                                threat = self.get_threat_level(nr, nc, player)
                                dist = abs(nr - center) + abs(nc - center)
                                all_defense_options.append((nr, nc, threat, dist))
                        
                        # 后端防守点
                        if bwd_stones:
                            br, bc = bwd_stones[-1]
                            nr, nc = br - dr, bc - dc
                            if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and self.board[nr][nc] == EMPTY:
                                threat = self.get_threat_level(nr, nc, player)
                                dist = abs(nr - center) + abs(nc - center)
                                all_defense_options.append((nr, nc, threat, dist))
        
        if not all_defense_options:
            return None
        
        # 优先选择：威胁最大的，然后距离中心最近的
        all_defense_options.sort(key=lambda x: (-x[2], x[3]))
        return all_defense_options[0][0], all_defense_options[0][1]
    
    def get_threat_level(self, row, col, player):
        """评估在(row, col)落子后的威胁等级"""
        if self.board[row][col] != EMPTY:
            return 0
        
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        max_threat = 0
        
        for dr, dc in directions:
            # 顺方向
            fwd = 0
            fwd_r, fwd_c = row + dr, col + dc
            while 0 <= fwd_r < BOARD_SIZE and 0 <= fwd_c < BOARD_SIZE:
                if self.board[fwd_r][fwd_c] == player:
                    fwd += 1
                elif self.board[fwd_r][fwd_c] == EMPTY:
                    break
                else:
                    break
                fwd_r += dr
                fwd_c += dc
            
            # 逆方向
            bwd = 0
            bwd_r, bwd_c = row - dr, col - dc
            while 0 <= bwd_r < BOARD_SIZE and 0 <= bwd_c < BOARD_SIZE:
                if self.board[bwd_r][bwd_c] == player:
                    bwd += 1
                elif self.board[bwd_r][bwd_c] == EMPTY:
                    break
                else:
                    break
                bwd_r -= dr
                bwd_c -= dc
            
            # 落子后，这条线上的总连续数 = fwd + bwd + 1（+1是新落的子）
            total = fwd + bwd + 1
            
            fwd_empty = (0 <= fwd_r < BOARD_SIZE and 0 <= fwd_c < BOARD_SIZE and 
                        self.board[fwd_r][fwd_c] == EMPTY)
            bwd_empty = (0 <= bwd_r < BOARD_SIZE and 0 <= bwd_c < BOARD_SIZE and 
                        self.board[bwd_r][bwd_c] == EMPTY)
            
            if total >= 5:
                max_threat = max(max_threat, 100)  # 五连
            elif total == 4:
                if fwd_empty and bwd_empty:
                    max_threat = max(max_threat, 98)  # 活四
                else:
                    max_threat = max(max_threat, 95)  # 冲四
            elif total == 3:
                if fwd_empty and bwd_empty:
                    max_threat = max(max_threat, 92)  # 活三
                elif fwd_empty or bwd_empty:
                    max_threat = max(max_threat, 80)  # 眠三
                else:
                    max_threat = max(max_threat, 50)
            elif total == 2:
                if fwd_empty and bwd_empty:
                    max_threat = max(max_threat, 75)  # 活二
                elif fwd_empty or bwd_empty:
                    max_threat = max(max_threat, 45)
                else:
                    max_threat = max(max_threat, 20)
            elif total == 1:
                if fwd_empty and bwd_empty:
                    max_threat = max(max_threat, 25)
                elif fwd_empty or bwd_empty:
                    max_threat = max(max_threat, 10)
        
        return max_threat
    
    def find_all_threats(self, player):
        threats = []
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                level = self.get_threat_level(r, c, player)
                if level > 0:
                    threats.append((r, c, level))
        # 同等级时优先选择离中心近的
        center = BOARD_SIZE // 2
        threats.sort(key=lambda x: (-x[2], abs(x[0]-center) + abs(x[1]-center)))
        return threats
    
    def count_nearby(self, r, c, player, radius=2):
        count = 0
        for dr in range(-radius, radius + 1):
            for dc in range(-radius, radius + 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE:
                    if self.board[nr][nc] == player:
                        count += 1
        return count
    
    def get_opening_move(self, player):
        """开局策略：前10步优先占领中心区域"""
        center = BOARD_SIZE // 2
        stone_count = sum(1 for r in range(BOARD_SIZE) for c in range(BOARD_SIZE) if self.board[r][c] != EMPTY)
        
        # 第一步下天元
        if stone_count == 0:
            return center, center
        
        # 第二步下附近（距离天元2格以内）
        if stone_count == 1:
            for r in range(BOARD_SIZE):
                for c in range(BOARD_SIZE):
                    if self.board[r][c] != EMPTY:
                        best, best_score = None, -1
                        for dr in range(-2, 3):
                            for dc in range(-2, 3):
                                nr, nc = r + dr, c + dc
                                if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and self.board[nr][nc] == EMPTY:
                                    dist = abs(nr - center) + abs(nc - center)
                                    score = 100 - dist * 5
                                    if score > best_score:
                                        best_score = score
                                        best = nr, nc
                        if best:
                            return best
        
        # 前10步：优先占领中心区域
        if stone_count < 10:
            # 找到最佳的中心区域落子点
            best_move = None
            best_score = -1
            
            for r in range(BOARD_SIZE):
                for c in range(BOARD_SIZE):
                    if self.board[r][c] != EMPTY:
                        continue
                    
                    # 检查是否是中心区域
                    dist_to_center = abs(r - center) + abs(c - center)
                    
                    # 中心区域内的位置
                    if (r, c) in CENTER_ZONE:
                        # 计算基础分：越接近中心分数越高
                        score = 100 - dist_to_center * 5
                        
                        # 靠近已有棋子的奖励
                        nearby = self.count_nearby(r, c, player, radius=2)
                        score += nearby * 20
                        
                        # 连接性加分
                        conn_score = self.get_connection_score(r, c, player)
                        score += conn_score * 0.3
                        
                        if score > best_score:
                            best_score = score
                            best_move = (r, c)
            
            if best_move:
                return best_move
        
        return None
    
    # ── Alpha-Beta 搜索系统 (新增 v24) ─────────────────────────────

    def _board_hash(self):
        """将当前棋盘转为哈希键（用于转置表）"""
        return ''.join(''.join(row) for row in self.board)

    def _get_candidates(self, player, min_level=0):
        """获取有序候选着法，用威胁等级排序用于剪枝效率"""
        candidates = set()
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if self.board[r][c] != EMPTY:
                    for dr in range(-2, 3):
                        for dc in range(-2, 3):
                            nr, nc = r + dr, c + dc
                            if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and self.board[nr][nc] == EMPTY:
                                candidates.add((nr, nc))
        if not candidates:
            return []

        scored = []
        for r, c in candidates:
            level = self.get_threat_level(r, c, player)
            if level < min_level:
                continue
            dist = abs(r - 7) + abs(c - 7)
            scored.append((r, c, level, dist))

        scored.sort(key=lambda x: (-x[2], x[3]))
        return [(r, c) for r, c, _, _ in scored]


    # ── v25 新增：必杀/必防快捷检测 ──────────────────────────────────

    def find_winning_move(self, player):
        """检测玩家是否能一步成五，返回该位置，否则返回 None"""
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if self.board[r][c] == EMPTY:
                    if self.get_threat_level(r, c, player) >= 100:
                        return (r, c)
        return None

    def find_block_four(self, player):
        """检测对手是否有四连（含冲四/活四）需要防守，返回堵截位置"""
        opponent = WHITE if player == BLACK else BLACK
        # 对手的四连威胁
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if self.board[r][c] == EMPTY:
                    if self.get_threat_level(r, c, opponent) >= 85:
                        return (r, c)
        return None

    # ── v25 新增：有序候选着点生成（剪枝效率关键）────────────────────

    def get_ordered_candidates(self, player):
        """返回排序后的候选着点列表，搜索顺序直接影响剪枝效率

        排序优先级：
        1. 我方冲四/活四（进攻机会）
        2. 对方冲四/活四（紧急防守）
        3. 我方活三（次级进攻）
        4. 对方活三（次级防守）
        5. 其他：按威胁等级降序，同级按中心距离排序
        """
        opponent = WHITE if player == BLACK else BLACK
        center = BOARD_SIZE // 2

        # 收集所有候选点及其评估
        candidates = []
        checked = set()

        # 扩大候选范围：从棋子周围3格内收集
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if self.board[r][c] != EMPTY:
                    for dr in range(-3, 4):
                        for dc in range(-3, 4):
                            nr, nc = r + dr, c + dc
                            if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE:
                                if self.board[nr][nc] == EMPTY and (nr, nc) not in checked:
                                    checked.add((nr, nc))
                                    my_level = self.get_threat_level(nr, nc, player)
                                    opp_level = self.get_threat_level(nr, nc, opponent)
                                    dist = abs(nr - center) + abs(nc - center)
                                    candidates.append((nr, nc, my_level, opp_level, dist))

        if not candidates:
            return []

        # 分层排序
        # 第一层：我方冲四/活四（level >= 85）
        tier1 = [(r, c) for r, c, my, opp, d in candidates if my >= 85]
        # 第二层：对方冲四/活四（opp >= 85）
        tier2 = [(r, c) for r, c, my, opp, d in candidates if my < 85 and opp >= 85]
        # 第三层：我方活三（75 <= my < 85）
        tier3 = [(r, c) for r, c, my, opp, d in candidates if my >= 75 and my < 85]
        # 第四层：对方活三（75 <= opp < 85）
        tier4 = [(r, c) for r, c, my, opp, d in candidates if opp >= 75 and opp < 85]
        # 第五层：其余，按威胁等级综合排序，同分则距离近优先
        tier5 = [(r, c, my + opp * 0.8, d) for r, c, my, opp, d in candidates
                 if my < 75 and opp < 75]
        tier5.sort(key=lambda x: (-x[2], x[3]))  # 同分按距离排
        tier5 = [((r, c), s) for r, c, s, d in tier5]

        ordered = []
        ordered.extend(tier1)
        ordered.extend(tier2)
        ordered.extend(tier3)
        ordered.extend(tier4)
        ordered.extend([p for p, _ in tier5])

        # 如果 ordered 太多（影响性能），限制数量
        if len(ordered) > 30:
            # 保留前30个（高优先级），其余舍弃
            ordered = ordered[:30]

        return ordered

    # ── v25 Alpha-Beta 搜索（核心）────────────────────────────────────

    def _alphabeta(self, board, depth, alpha, beta, maximizing, player):
        """带节点限制的 Alpha-Beta 搜索"""
        self._nodes += 1
        if self._nodes > self._node_limit:
            return self._static_evaluate(board, player), None

        opponent = WHITE if player == BLACK else BLACK
        board_key = ''.join(''.join(row) for row in board)

        # 转置表查找（只用于同深度或更深）
        if board_key in self.tt:
            entry = self.tt[board_key]
            if entry['depth'] >= depth:
                flag, score = entry['flag'], entry['score']
                if flag == 'exact':
                    return score, entry.get('move')
                elif flag == 'lower' and score >= beta:
                    return score, entry.get('move')
                elif flag == 'upper' and score <= alpha:
                    return score, entry.get('move')

        # 终止检测
        if maximizing:
            if self._has_five(board, player):
                return 100000, None
        else:
            if self._has_five(board, opponent):
                return 100000, None

        if depth == 0:
            score = self._static_evaluate(board, player)
            self.tt[board_key] = {'depth': 0, 'flag': 'exact', 'score': score}
            return score, None

        # 获取有序候选着点
        old_board = self.board
        self.board = board
        moves = self.get_ordered_candidates(player if maximizing else opponent)
        self.board = old_board

        if not moves:
            score = self._static_evaluate(board, player)
            self.tt[board_key] = {'depth': depth, 'flag': 'exact', 'score': score}
            return score, None

        best_move = None

        if maximizing:
            value = -float('inf')
            for r, c in moves:
                board[r][c] = player
                val, _ = self._alphabeta(board, depth - 1, alpha, beta, False, player)
                board[r][c] = EMPTY
                if val > value:
                    value = val
                    best_move = (r, c)
                alpha = max(alpha, value)
                if alpha >= beta:
                    break  # beta 剪枝
            flag = 'exact'
            self.tt[board_key] = {'depth': depth, 'flag': flag, 'score': value, 'move': best_move}
            return value, best_move
        else:
            value = float('inf')
            for r, c in moves:
                board[r][c] = opponent
                val, _ = self._alphabeta(board, depth - 1, alpha, beta, True, player)
                board[r][c] = EMPTY
                if val < value:
                    value = val
                    best_move = (r, c)
                beta = min(beta, value)
                if alpha >= beta:
                    break  # alpha 剪枝
            flag = 'exact'
            self.tt[board_key] = {'depth': depth, 'flag': flag, 'score': value, 'move': best_move}
            return value, best_move

    def _static_evaluate(self, board, player):
        """静态评估函数 - 供 v25 Alpha-Beta 搜索使用

        评估维度：
        1. 我的最佳威胁等级
        2. 对手的最佳威胁等级
        3. 我的威胁总和
        4. 对手的威胁总和
        """
        opponent = WHITE if player == BLACK else BLACK

        my_best = 0
        my_sum = 0
        opp_best = 0
        opp_sum = 0

        # get_threat_level 需要 self.board，临时切换
        old_board = self.board
        self.board = board
        try:
            for r in range(BOARD_SIZE):
                for c in range(BOARD_SIZE):
                    if board[r][c] == EMPTY:
                        my_level = self.get_threat_level(r, c, player)
                        opp_level = self.get_threat_level(r, c, opponent)
                        my_best = max(my_best, my_level)
                        opp_best = max(opp_best, opp_level)
                        if my_level >= 25:
                            my_sum += my_level
                        if opp_level >= 25:
                            opp_sum += opp_level

            score = 0

            # 五连检测
            if my_best >= 100 or opp_best >= 100:
                if my_best > opp_best:
                    return 90000
                elif opp_best > my_best:
                    return -90000
                else:
                    return 0

            # 威胁等级评分
            if my_best >= 95:
                score += 15000
            elif my_best >= 85:
                score += 8000
            elif my_best >= 75:
                score += 3000

            if opp_best >= 95:
                score -= 15000
            elif opp_best >= 85:
                score -= 10000
            elif opp_best >= 75:
                score -= 4000
            elif opp_best >= 45:
                score -= 500

            # 威胁总和评分
            score += my_sum * 1.5
            score -= opp_sum * 1.5

            return score
        finally:
            self.board = old_board

    def _has_five(self, board, player):
        """检查玩家是否已五连"""
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if board[r][c] != player:
                    continue
                for dr, dc in directions:
                    count = 1
                    nr, nc = r + dr, c + dc
                    while 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and board[nr][nc] == player:
                        count += 1
                        nr += dr
                        nc += dc
                    if count >= 5:
                        return True
        return False

    def find_best_move(self, player=BLACK):
        """找到最佳落子位置 - Alpha-Beta 搜索 v25

        优先级（逐级检查，不过渡到下一级）：
        1. 成五必杀：自己能一步成五 → 直接下
        2. 必防对手成五：对手能一步成五 → 必须堵
        3. 四连防守：对手有冲四/活四 → 必须堵
        4. Alpha-Beta 搜索（depth=4）：综合评估选最优
        """
        opponent = WHITE if player == BLACK else BLACK

        # 1. 我能赢 → 直接下
        win = self.find_winning_move(player)
        if win:
            return win

        # 2. 对手要赢 → 必须防
        block = self.find_winning_move(opponent)
        if block:
            return block

        # 3. 对手四连 → 必须防
        block4 = self.find_block_four(player)
        if block4:
            return block4

        # 4. Alpha-Beta 搜索
        self.tt = {}
        self._nodes = 0
        self._node_limit = 12000

        # 深拷贝棋盘用于搜索
        board_copy = [row[:] for row in self.board]

        candidates = self.get_ordered_candidates(player)
        if not candidates:
            return 7, 7  # 天元 fallback

        best_move = None
        best_score = -float('inf')
        alpha = -float('inf')
        beta = float('inf')

        for r, c in candidates:
            board_copy[r][c] = player
            score, _ = self._alphabeta(board_copy, depth=3, alpha=alpha, beta=beta,
                                       maximizing=False, player=player)
            board_copy[r][c] = EMPTY
            if score > best_score:
                best_score = score
                best_move = (r, c)
                alpha = max(alpha, score)

        return best_move if best_move else (7, 7)
    
    def evaluate(self, player=BLACK):
        """评估函数 - 攻守平衡版本 v22
        增加：
        - 位置权重（中心比角落重要）
        - 连接性评分（连成链的价值）
        - 平衡攻防比例
        """
        opponent = WHITE if player == BLACK else BLACK
        center = BOARD_SIZE // 2
        candidates = set()
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if self.board[r][c] != EMPTY:
                    for dr in range(-3, 4):
                        for dc in range(-3, 4):
                            nr, nc = r + dr, c + dc
                            if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and self.board[nr][nc] == EMPTY:
                                candidates.add((nr, nc))
        
        if not candidates:
            return center, center
        
        best_score = -float('inf')
        best_moves = []
        
        for r, c in candidates:
            my_level = self.get_threat_level(r, c, player)
            opp_level = self.get_threat_level(r, c, opponent)
            
            # 预测对手的下一步威胁
            self.board[r][c] = player
            opp_next = self.find_all_threats(opponent)
            opp_next_max = opp_next[0][2] if opp_next else 0
            self.board[r][c] = EMPTY
            
            score = 0
            
            # ====== 进攻评分（增强）======
            if my_level >= 100:  # 成五
                score += 50000
            elif my_level >= 95:  # 活四
                score += 15000
            elif my_level >= 85:  # 冲四
                score += 10000
            elif my_level >= 75:  # 活三
                score += 5000
            elif my_level >= 45:  # 眠三
                score += 1000
            
            # ====== 防守评分 ======
            if opp_next_max >= 100:
                score -= 50000
            elif opp_next_max >= 85:  # 对手冲四/活四
                score -= 25000
            elif opp_next_max >= 75:  # 对手活三
                score -= 8000
            elif opp_next_max >= 45:  # 对手眠三
                score -= 2000
            elif opp_next_max >= 25:  # 对手2连
                score -= 500
            
            # 当前落子后对手的即时威胁
            if opp_level >= 100:
                score -= 50000
            elif opp_level >= 85:
                score -= 15000
            elif opp_level >= 75:
                score -= 5000
            elif opp_level >= 45:
                score -= 1000
            
            # ====== 新增：位置权重 ======
            score += POSITION_WEIGHTS[r][c]
            
            # ====== 新增：连接性评分 ======
            conn_score = self.get_connection_score(r, c, player)
            score += conn_score
            
            # 靠近已有棋子的奖励
            score += self.count_nearby(r, c, player) * 30
            score += self.count_nearby(r, c, opponent) * 20
            
            # 中心位置偏好（备用）
            dist = abs(r - center) + abs(c - center)
            score += max(0, 30 - dist * 2)
            
            if score > best_score:
                best_score = score
                best_moves = [(r, c)]
            elif score == best_score:
                best_moves.append((r, c))
        
        if best_moves:
            # 随机选择一个最佳着法（加入随机性）
            best_moves.sort(key=lambda x: abs(x[0]-center) + abs(x[1]-center))
            # 从前3个最佳着法中随机选择
            choice_count = min(3, len(best_moves))
            return random.choice(best_moves[:choice_count])
        return center, center
    
    def get_move_notation(self, row, col):
        # 15x15棋盘: A-H, J-P (跳过I) = 15列
        if 0 <= col <= 14:
            cols = 'ABCDEFGHJKLMNOP'
            return f"{cols[col]}{row+1}"
        else:
            return f"?{row+1}"


def main():
    board_str = sys.stdin.read()
    if not board_str.strip():
        print("H8")
        return
    ai = GomokuAI(board_str)
    
    # 判断AI是黑棋还是白棋
    # 如果白棋数量 > 黑棋数量，说明白棋刚下了，轮到黑棋
    # 如果黑棋数量 >= 白棋数量，说明黑棋刚下了（或刚开始），轮到白棋
    black_count = sum(1 for r in range(BOARD_SIZE) for c in range(BOARD_SIZE) if ai.board[r][c] == BLACK)
    white_count = sum(1 for r in range(BOARD_SIZE) for c in range(BOARD_SIZE) if ai.board[r][c] == WHITE)
    
    if white_count > black_count:
        player = BLACK  # 白刚下完，轮到黑
    else:
        player = WHITE  # 黑刚下完（或刚开始），轮到白
    
    row, col = ai.find_best_move(player)
    if row is None:
        print("PASS")
        return
    print(ai.get_move_notation(row, col))


if __name__ == "__main__":
    main()
