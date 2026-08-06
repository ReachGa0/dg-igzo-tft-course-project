"""Build a printable PDF companion for the editable 10-slide deck."""

import base64
import mimetypes
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "report" / "assets"
HTML_OUT = ROOT / "ppt" / "slides_for_pdf.html"


def image(name: str) -> str:
    path = ASSETS / name
    mime, _ = mimetypes.guess_type(path.name)
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f'<img src="data:{mime};base64,{data}" alt="{name}" />'


def slide(number: int, title: str, body: str, images: tuple[str, ...] = ()) -> str:
    gallery = "".join(image(name) for name in images)
    return f'<section class="slide"><div class="bar"></div><div class="number">{number:02d}</div><h1>{title}</h1>{body}{gallery}</section>'


slides = [
    slide(1, "基于双栅 IGZO TFT 的二维器件模型与单极性逻辑教学 PDK", "<p class=subtitle>课程项目阶段性报告与可复现证据汇总</p><div class=cards><div><b>范围</b><br>仅 n 型 IGZO；二维优先；普通笔记本可运行</div><div><b>证据</b><br>E2/E3 教学模型数值闭环；失败结果原样保留</div><div class=fail><b>当前门</b><br>C00 R04 锚点未通过，G3 关闭</div></div><p class=footer>提交主体：课程报告 HTML | IGZO only</p>"),
    slide(2, "研究问题与阶段边界", "<div class=cards><div><b>器件层</b><br>双栅 IGZO 漂移扩散与准静态陷阱<br>输出：I-V、状态和守恒</div><div><b>模型层</b><br>教学紧凑模型与 ngspice/GPL Xyce 对照<br>输出：误差与路线差异</div><div class=fail><b>电路层</b><br>双栅 IGZO 有源负载反相器<br>输出：VTC、延迟、功耗</div></div><h2>阶段门原则</h2><ul><li>C00 未通过，不能把环振、全加器或版图写成已验证。</li><li>没有实验数据时，参数和趋势只限教学模型或文献约束敏感性。</li></ul>"),
    slide(3, "双栅 IGZO 器件与模型边界", "<div class=columns><div><h2>结构与耦合</h2><ul><li>n 型 IGZO；底栅/顶栅双介质耦合。</li><li>二维漂移扩散、准静态陷阱电荷和电流守恒。</li><li>Al2O3 物理厚度与 SPICE 有效 TOX 分开记录。</li></ul></div><div><h2>模型有效域</h2><div class=mini>300 K 名义温度</div><div class=mini>VDS = 0--0.2 V</div><div class=mini>L = 8--12 um</div><div class=mini>IGZO only</div></div></div><p class=warning>禁止外推：实验拟合、真实迁移率/DOS/接触参数、完整 P2/T03 物理结论。</p>"),
    slide(4, "双栅基线：从器件到耦合", "<p>T02-C：318 次 DC、248 点和 6 个状态；双向曲线、回程和耦合指标由独立检查复算。</p>", ("tcad_t02_c_bidirectional_families.png", "tcad_t02_c_state_maps.png")),
    slide(5, "T03 敏感性结果", "<p>五组参数均限定为冻结 IGZO 教学模型内的数值代理。趋势是数值诊断，不是物理机制或实验校准。</p>", ("tcad_t03_p1_bias_sensitivity.png", "tcad_t03_p2_bulk_traps_formal_v3_sensitivity.png", "tcad_t03_p5_temperature_sensitivity.png")),
    slide(6, "M00/M01：紧凑模型与两路线对照", "<div class=cards><div><b>M00</b><br>R02 runner E2 / 独立 E3</div><div><b>M01</b><br>ngspice + GPL Xyce</div><div class=fail><b>边界</b><br>不等同方程身份或真实器件参数</div></div>", ("m00_compact_model_fit_r02.png", "m01_open_source_cross_check_r03.png")),
    slide(7, "C00 R04：完整执行但锚点失败", "<div class=cards><div><b>执行证据</b><br>4 个串行进程均返回 0；原始表、图和哈希完整。</div><div class=fail><b>锚点结果</b><br>VOH 约 0.0912 V；VOL 约 0.0206 V；最大增益约 0.884。</div><div class=fail><b>失败门</b><br>0 个单位增益交点；VIL/VIH/NM 无法提取。</div></div><p class=warning>33/36 E0/FAIL：不是工具崩溃或不收敛。</p>", ("c00_active_load_inverter_vtc_r04.png",)),
    slide(8, "C00 瞬态与 G3 阶段门", "<ul><li>输出约 0.022--0.057 V，rise/fall crossing 均不存在。</li><li>tPHL/tPLH 保留为空，不插值、不估算。</li><li>C00 未通过，C01--C03、版图和 PEX 关闭。</li></ul><p class=warning>负结果是阶段门证据，不是仿真器失败。</p>", ("c00_active_load_inverter_transient_r04.png",)),
    slide(9, "交付边界与风险控制", "<div class=cards><div><b>已完成</b><br>二维器件数值<br>T03 五组敏感性<br>M00/M01 教学模型<br>完整证据矩阵</div><div class=fail><b>明确未完成</b><br>合格 C00 反相器<br>组合逻辑与环振<br>版图/LVS/PEX<br>HZO 扩展</div><div><b>不能夸大</b><br>实验校准<br>物理参数提取<br>工艺签核<br>真实工作频率</div></div><p class=footer>正式主体：课程报告 HTML；完整审计附件和 Git 哈希链随项目保留。</p>"),
    slide(10, "最终结论", "<h2>器件与模型主线已闭环；有源负载逻辑锚点不合格。</h2><div class=cards><div><b>贡献 1</b><br>二维双栅 IGZO 器件、陷阱与敏感性证据链。</div><div><b>贡献 2</b><br>行为紧凑模型和开源两路线对照。</div><div class=fail><b>贡献 3</b><br>正式 C00 失败暴露设计裕量不足并关闭下游门。</div></div><p class=footer>证据等级：器件/模型主线 E2--E3；C00 R04 runner E0/FAIL。</p>"),
]


css = """
@page{size:13.333in 7.5in;margin:0}*{box-sizing:border-box}body{margin:0;background:#e8eef0;color:#1f2a33;font-family:"Microsoft YaHei",Arial,sans-serif}.slide{position:relative;width:13.333in;height:7.5in;padding:.55in .7in;background:#fff;break-after:page;page-break-after:always;overflow:hidden}.slide:last-child{break-after:auto;page-break-after:auto}.bar{position:absolute;top:0;left:0;width:100%;height:.16in;background:#087b78}.number{position:absolute;right:.62in;top:.36in;color:#087b78;font-weight:700}h1{margin:0 0 .18in;color:#142336;font-size:27pt;line-height:1.2}h2{margin:.18in 0 .12in;color:#164f73;font-size:18pt}p{font-size:15pt;line-height:1.5}.subtitle{font-size:19pt;color:#b6e0e0;margin-top:.28in}.cards{display:flex;gap:.22in;margin-top:.32in}.cards>div{flex:1;min-height:1.35in;padding:.18in;background:#f1f6f7;border:1px solid #d2dfe1;border-radius:6px;font-size:14pt;line-height:1.45}.cards b{color:#087b78;font-size:16pt}.cards .fail{border-top:4px solid #b83838}.columns{display:grid;grid-template-columns:1fr 1fr;gap:.45in}.mini{display:inline-block;margin:.08in;padding:.12in .2in;background:#eaf5f4;color:#087b78;font-weight:700}.warning{color:#b83838;font-weight:700;font-size:17pt}.footer{position:absolute;left:.72in;right:.72in;bottom:.32in;color:#5c6971;font-size:11pt}ul{font-size:16pt;line-height:1.65;padding-left:.35in}img{display:inline-block;width:31%;height:4.6in;object-fit:contain;margin:.2in .8% 0;border:1px solid #d5e0e3}img:first-of-type{width:63%}.slide:has(img:nth-of-type(2)) img{height:4.55in}.slide:has(img:nth-of-type(3)) img{width:31%;height:4.35in}.slide:has(img:only-of-type) img{width:72%;height:4.9in;display:block;margin:.22in auto 0}@media print{body{background:#fff}}
"""

css += ".slide:has(img:only-of-type) img{height:3.55in!important}"


html = f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>双栅 IGZO TFT 答辩 slides</title><style>{css}</style></head><body>{"".join(slides)}</body></html>'
HTML_OUT.write_text(html, encoding="utf-8")
print(HTML_OUT)
