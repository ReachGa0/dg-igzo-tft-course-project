# 报告图片工作目录

报告工作稿可使用相对于 `report/src/实验报告_草稿.xhtml` 的图片路径，例如：

```html
<img src="../assets/Fig07_tcad_potential.png" alt="图7 双栅结构二维电势" />
```

图片必须由可追溯 CSV/VTK/GDS 生成，命名包含图号。`make report` 会把它们转为 Base64 写进最终 HTML；这里的外部图片不会作为最终报告单独提交。
