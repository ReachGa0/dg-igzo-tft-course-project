# 报告图片工作目录

所有章节统一使用相对于 `report/` 的图片路径：

```html
<img src="assets/Fig07_tcad_potential.png" alt="图7 双栅结构二维电势" />
```

图片必须由可追溯 CSV/VTK/GDS 生成，命名包含图号。`make report-check` 检查路径和 `alt`，`make report` 将图片转为 Base64 写入最终单文件。这里的源图片随完整工程保留，但正式报告不会依赖它们才能显示。
