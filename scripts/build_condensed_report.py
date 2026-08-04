"""Build a 20-page condensed, self-contained course report."""

import base64
import mimetypes
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "report" / "assets"
OUT = ROOT / "report" / "final" / "项目精简报告.html"


def img(name: str, alt: str) -> str:
    path = ASSETS / name
    mime, _ = mimetypes.guess_type(path.name)
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f'<figure><img src="data:{mime};base64,{encoded}" alt="{alt}" /><figcaption>{alt}</figcaption></figure>'


def page(number: int, title: str, body: str, image_name: str | None = None, alt: str = "") -> str:
    figure = img(image_name, alt) if image_name else ""
    return f'<section class="page"><div class="page-no">{number:02d}</div><h2>{title}</h2>{body}{figure}</section>'


pages = [
    page(1, "项目名称与摘要", "<h1>基于双栅 IGZO TFT 的二维器件模型、紧凑模型与单极性逻辑教学 PDK</h1><p class=lead>本报告是完整报告的精简阅读版。项目以二维 n 型 IGZO 教学模型为主线，完成器件双栅耦合、五组参数敏感性、教学紧凑候选和两开源路线对照；C00 有源负载反相器完整执行但未通过预注册逻辑门，因此后续逻辑、版图与 HZO 未纳入本次提交。</p><div class=chips><span>IGZO only</span><span>二维优先</span><span>教学模型</span><span>FAIL 保留</span></div>"),
    page(2, "研究问题与有效范围", "<p>核心问题不是在没有实验数据时制造“真实器件参数”，而是以可追溯输入回答：双栅偏压、陷阱、接触、几何和温度在冻结二维模型中怎样改变数值代理；这些结果能否形成受限紧凑候选，并支持有源负载逻辑的可行性评估。</p><table><tr><th>纳入提交</th><td>S00、T01--T03、M00、M01、C00 R04、HTML/PDF/PPT</td></tr><tr><th>不纳入提交</th><td>C01--C03、GDS、DRC/LVS、PEX、HZO</td></tr><tr><th>证据边界</th><td>不主张实验校准、物理参数提取、流片签核或真实电路频率</td></tr></table>"),
    page(3, "阶段 DAG 与证据规则", "<pre>S00 -> T01 -> T02 -> T03 -> M00 -> M01 -> C00 FAIL -> R00</pre><p>每一阶段保存输入、脚本、原始输出、处理表、图和 PASS/FAIL 报告。E2 表示项目运行证据，E3 表示合同或独立复核；静态合同不能替代器件或电路仿真。</p><p class=boundary>C00 未通过即关闭环振、全加器、版图和 PEX。本项目严格执行该 G3 门。</p>"),
    page(4, "二维器件模型与口径", "<p>器件层采用二维 Poisson 方程与电子连续性方程。电势以 V 表示，电子浓度以 cm<sup>-3</sup> 表示，电流按二维宽度归一化为 A/cm。底栅和顶栅共同调制沟道势垒；界面态和体陷阱均是准静态教学电荷项。</p><table><tr><th>材料</th><td>n 型 IGZO only</td></tr><tr><th>名义温度</th><td>300 K（P5 单独比较 250/300/350 K）</td></tr><tr><th>有效域</th><td>VDS=0--0.2 V，L=8--12 um</td></tr></table><p class=boundary>该模型不是实验拟合，30 nm Al2O3 物理厚度与 10 nm SPICE 有效口径分开记录。</p>"),
    page(5, "T01：单栅漂移扩散基线", "<p>T01 依次完成低偏压烟雾、栅压续算、界面网格收敛、Id-Vd 采样和内部状态。interface_4x/8x 在高栅压点的最大电流差为 0.01639%；最终状态、守恒和网格证据形成后续双栅的数值基线。</p>", "tcad_t01_d_idvd.png", "T01 单栅 Id-Vd 曲线与网格复核"),
    page(6, "T02：双栅耦合与双向偏压", "<p>T02-C 完成 318 次 DC、248 个 transfer 点和 6 个状态。零副栅 VTH 数值代理为 0.263857 V；受控副栅变化产生正/负阈值位移。双向曲线、回程和互易关系由独立检查复算。</p><p class=boundary>VTH、SS、gm 仅是冻结教学模型的提取代理，不能外推为实测器件指标。</p>", "tcad_t02_c_bidirectional_families.png", "T02-C 双栅双向曲线与受限提取"),
    page(7, "T03-P1：偏压与电容分配", "<p>P1-BIAS 以 VBG=-0.4 至 +0.4 V 扫描，五点 VTH 代理斜率为 -0.940554 V/V、R2=0.995712。P1-CAP-RATIO 固定总耦合，仅改变有效 Ctop/Cbottom=0.5 至 2；VTH 严格下降、gm 严格上升。</p><p>这两组是双栅耦合的数值敏感性，不是测量电容或介质常数提取。</p>", "tcad_t03_p1_bias_sensitivity.png", "T03-P1 固定底栅偏压敏感性"),
    page(8, "T03-P2：界面态与方程冒烟", "<p>底界面 DIT 子阶段先冻结来源、单位、三点与方程；正式敏感性使用零控制加 3 个文献约束点，完成 4 器件、164 次 DC、124 点和 4 个状态。合同、运行器与独立检查均通过。</p><p class=boundary>界面态密度来自文献约束，并非本项目从实验反演得到的 DOS。</p>", "tcad_t03_p2_dit_formal_sensitivity.png", "T03-P2 DIT 正式敏感性"),
    page(9, "T03-P2：隔离体陷阱", "<p>Bulk-trap 方程烟雾先验证零控制、NTA 参考和 NGA 参考。正式 V3 使用两组零控制和 NTA/NGA 各三点，完成 8 器件、456 次收敛 DC、376 点、8 状态、48 个 VTK；runner 17/17、独立 16/16 PASS。</p><p>NTA 中 VTH/SS 代理递增而 gm 递减；NGA 的 SS 轻微递减作为诊断保留，不改写为物理机制。</p>", "tcad_t03_p2_bulk_traps_formal_v3_sensitivity.png", "T03-P2 NTA/NGA 正式 V3 敏感性"),
    page(10, "T03-P3：接触电阻教学代理", "<p>P3 V1 的零漏压相对守恒门不适用，失败完整保留。V2 只分离零/非零漏压验收适用域，保持 0/0.5/4.5 kOhm*um 三点，完成 12 器件、243 次 DC、156 点；runner 25/25、独立 20/20 PASS。</p><p>高阻点高栅电流代理下降 0.161396%，仅反映对称串联电阻数值响应，不是 TLM、金属或势垒提取。</p>", "tcad_t03_p3_contact_v2_sensitivity.png", "T03-P3 V2 接触电阻教学敏感性"),
    page(11, "T03-P4/P5：长度与温度", "<p>P4 以 L=8/10/12 um 完成 123 次 DC、93 点和独立检查；理想 1/L 诊断失败被保留，不作为完成门。P5 只改变热电压 Vt，250/300/350 K 完成 3 器件、123 次 DC、93 点；300 K 精确回归 T02-C。</p><p>温度曲线的 VTH/SS/gm/Ion/Ioff 均是 Vt-only 数值响应，不建立真实温度依赖。</p>", "tcad_t03_p5_temperature_sensitivity.png", "T03-P5 三点温度敏感性"),
    page(12, "T03 汇总与可解释边界", "<table><tr><th>参数组</th><th>完成证据</th><th>不允许的结论</th></tr><tr><td>P1</td><td>偏压与耦合分配 E3</td><td>物理电容测量</td></tr><tr><td>P2</td><td>DIT 与 bulk E3</td><td>实验 DOS 或动态陷阱</td></tr><tr><td>P3</td><td>串联电阻代理 E3</td><td>TLM/接触势垒</td></tr><tr><td>P4/P5</td><td>长度、Vt-only 温度 E3</td><td>缩放律/真实温度律</td></tr></table><p>五组参数均在二维、未校准、普通笔记本可运行的教学边界内闭合。</p>"),
    page(13, "M00：教学紧凑模型", "<p>M00 R02 使用 9 条 train 曲线/163 点与 4 条完整条件 holdout/70 点，固定一阶长度因子，避免以 holdout 调参。runner 24/24 PASS，独立检查 20/20 PASS；线性/对数、VTH、gm、边界与候选生成均被记录。</p><p class=boundary>10 个系数仅是教学代理系数，不是迁移率、VTH、DOS、接触或温度物理参数。</p>", "m00_compact_model_fit_r02.png", "M00 R02 教学紧凑模型曲线"),
    page(14, "M01：开源两路线对照", "<p>M01 R03 在同一冻结 247 行目标上使用 ngspice 与 GPL Xyce。一个串行 ngspice 与一个串行 Xyce 进程完成，独立 checker 重建两份网表、解析 raw/PRN、重算 247+247 行、30 个指标和差异表。</p><p>在 portable 候选上最大绝对/对数差为 4.37069e-19 A/cm 和 2.75335e-14 decade。该一致性只适用于该行为候选与注册域。</p>", "m01_open_source_cross_check_r03.png", "M01 R03 两开源路线对照"),
    page(15, "C00：双栅有源负载拓扑", "<p>C00 固定两个 n 型双栅 IGZO 行为候选：驱动管由 VIN 控制下拉；负载管漏端接 VDD、底栅接 VDD、顶栅由 V_TOP_LOAD 编程。正式网格覆盖 2 档 VDD、3 档负载顶栅、3 档宽度比和 2 档 Cload。</p><p>锚点在执行前固定为 VDD=0.2 V、负载顶栅=0.2 V、Wload/Wdriver=0.125、Cload=1 pF；禁止事后替换最佳案例。</p>"),
    page(16, "C00：正式 DC 结果", "<p>R04 修正了历史 Xyce 重复 TIME 的解析边界后，两个路线各落盘 1818 行 DC、36 行静态指标和完整路线差异。四个过程均返回 0，输出轴、表、图和哈希完整。</p><p class=boundary>冻结锚点 VOH 约 0.0912 V、VOL 约 0.0206 V、最大增益约 0.884，0 个单位增益交点。因此 VIL/VIH/噪声裕量无法按合同提取。</p>", "c00_active_load_inverter_vtc_r04.png", "C00 R04 VTC 与静态功耗失败证据"),
    page(17, "C00：正式瞬态结果", "<p>两路线各落盘 21636 行瞬态、72 行瞬态指标与完整差异表。冻结锚点在低/高输入采样时的输出约为 0.057/0.022 V；输出没有 50% crossing。</p><p>tPHL/tPLH 以空字段和显式缺失状态保留，不以视觉趋势或插值生成延迟。该处理避免把不合格的摆幅写成逻辑速度结果。</p>", "c00_active_load_inverter_transient_r04.png", "C00 R04 瞬态输出与供电功耗失败证据"),
    page(18, "C00 失败的工程含义", "<p>R04 返回 33/36、E0/FAIL。失败项是静态锚点与瞬态锚点资格门及其派生完成门；不是仿真器、收敛、原始轴、parser、产物完整性或路线一致性失败。</p><table><tr><th>通过</th><td>4 个开源进程、所有注册案例、两路线输出、26 个哈希</td></tr><tr><th>失败</th><td>增益小于 1、无单位增益交点、无瞬态输出 crossing</td></tr><tr><th>后果</th><td>G3 关闭；不运行 C01--C03、版图、PEX、HZO</td></tr></table>"),
    page(19, "复现、交付与人工核对", "<p>提交包包含配置、脚本、原始/处理结果、正式报告、精华版、PPTX 和 Git 哈希。总检查命令为 <code>make check</code>，报告结构检查为 <code>make report-check</code>。正式 runner 均有唯一运行约束，不因复现便利而重跑。</p><p>提交前人工核对完整报告封面的姓名、学号/班级和指导教师，并确认 PDF/PPT 字体和页面排版。</p>"),
    page(20, "最终结论", "<p>项目以可复现的二维 IGZO 教学模型完成了器件与模型主线，并以完整双路线证据得到 C00 有源负载锚点不合格的负结论。这个结论比未经验证的后续逻辑或版图占位更可靠。</p><div class=boundary><strong>最终边界：</strong>本项目不主张实验校准、真实器件物理参数、原生 Level 61、可流片 PDK、合格逻辑单元或 HZO 结果。任何 C00 恢复必须在新合同中重新冻结设计变量，不能回写 R04。</div><p class=note>提交版本：d3f8cbc。完整报告保留全部审计细节；本精简报告用于教师连续阅读。</p>"),
]

html = """<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"UTF-8\"/><meta name=\"viewport\" content=\"width=device-width,initial-scale=1.0\"/><title>双栅 IGZO TFT 课程项目精简报告</title><style>
:root{--ink:#172a38;--blue:#164f73;--teal:#087b78;--line:#d5e0e3;--warn:#b84a32;--muted:#5d6d78}*{box-sizing:border-box}body{margin:0;background:#edf3f4;color:var(--ink);font-family:\"Microsoft YaHei\",Arial,sans-serif;line-height:1.72}main{width:min(1050px,calc(100% - 36px));margin:20px auto;background:white;padding:42px 54px}.page{position:relative;min-height:930px;padding:8px 0 25px;break-after:page;page-break-after:always}.page:last-child{break-after:auto;page-break-after:auto}.page-no{position:absolute;right:0;top:0;color:var(--teal);font-weight:700}h1{font-size:32px;line-height:1.35;color:var(--blue);margin:25px 0}h2{color:var(--blue);font-size:25px;border-bottom:2px solid var(--line);padding-bottom:8px;margin:15px 0 18px}p{margin:10px 0}.lead{font-size:19px}.chips{display:flex;gap:10px;flex-wrap:wrap;margin:25px 0}.chips span{padding:7px 12px;background:#eaf5f4;color:var(--teal);font-weight:700}table{width:100%;border-collapse:collapse;margin:18px 0}th,td{padding:10px;border:1px solid var(--line);vertical-align:top;overflow-wrap:anywhere}th{width:27%;background:#edf4f6;color:var(--blue)}figure{margin:22px 0;break-inside:avoid;page-break-inside:avoid}img{display:block;width:100%;max-height:590px;object-fit:contain;border:1px solid var(--line)}figcaption{font-size:14px;color:var(--muted);margin-top:7px}.boundary{margin:18px 0;padding:15px 18px;background:#fff6dd;border-left:5px solid #c98b16}.note{color:var(--muted)}pre{padding:18px;background:#f3f6f7;white-space:pre-wrap;font-family:Consolas,monospace}@media(max-width:720px){main{width:100%;margin:0;padding:28px 22px}.page{min-height:auto}.page-no{position:static;text-align:right}h1{font-size:25px}h2{font-size:22px}}@media print{body{background:white}main{width:auto;margin:0;padding:14mm}.page{min-height:250mm}h2{break-after:avoid;page-break-after:avoid}}</style></head><body><main>""" + "".join(pages) + "</main></body></html>"
OUT.write_text(html, encoding="utf-8")
print(OUT)
