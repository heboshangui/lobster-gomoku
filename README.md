# 🦞 lobster-gomoku

基于 Alpha-Beta 剪枝的五子棋 AI（Python 实现）。

## 主要特性

- Alpha-Beta 搜索（depth=4）
- 转置表（TT）优化
- 威胁等级评估函数（活四/冲四/活三/眠三分级）
- 候选点排序（剪枝效率优化）
- 成五/四连 必杀检测

## 版本历史

- **v25** (2026-03-22): Alpha-Beta 搜索升级 + 威胁等级重写
- **v20**: 贪心策略 + 评估函数

## 文件

- `gomoku_ai.py` - 主AI逻辑
- `gomoku_runner.py` - 对局入口

## License

MIT
