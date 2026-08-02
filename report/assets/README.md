# 报告图片工作目录

所有章节统一使用相对于 `report/` 的图片路径：

```html
<img src="assets/Fig07_tcad_potential.png" alt="图7 双栅结构二维电势" />
```

图片必须由可追溯 CSV/VTK/GDS 生成，命名包含图号。`make report-check` 检查路径和 `alt`，`make report` 将图片转为 Base64 写入最终单文件。这里的源图片随完整工程保留，但正式报告不会依赖它们才能显示。

当前文件分两类：

- 正式当前图：章节 XHTML 直接引用的无失败后缀 PNG。
- 失败审计副本：文件名含 `_v1_failed` 或 `_v1_ss_linearity_failed`，只保存首次失败证据，不插入当前正文。

三对审计图字节级相同是预期行为：P4 V1 的失败只在完成性诊断，器件状态没有重跑；P2-DIT V1 的失败只在 SS 提取窗口，状态数据没有改变。因此 P4 的 sensitivity/state 两对和 P2-DIT 的 state 一对与最终图相同；P2-DIT sensitivity 因 SS 提取改变而不相同。不要把这些归档副本计作新增物理结果或重复报告图。
