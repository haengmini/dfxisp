#!/usr/bin/env python3
"""Build the Korean DFXISP research proposal as a self-contained PDF."""

from pathlib import Path
import textwrap

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_plan" / "DFXISP_연구계획서.pdf"
RESULTS = ROOT / "isppipeline" / "hls" / "results"
FONT = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"
if not Path(FONT).exists():
    FONT = font_manager.findfont("NanumGothic")
if not Path(FONT_BOLD).exists():
    FONT_BOLD = FONT

font_manager.fontManager.addfont(FONT)
font_manager.fontManager.addfont(FONT_BOLD)
plt.rcParams.update({
    "font.family": "NanumGothic",
    "axes.unicode_minus": False,
    "figure.facecolor": "white",
})

NAVY = "#17324D"
BLUE = "#246BCE"
CYAN = "#17A2B8"
ORANGE = "#F28E2B"
RED = "#D9534F"
GREEN = "#2E8B57"
LIGHT = "#EEF4FA"
GRAY = "#5F6B76"
PAGE = (8.27, 11.69)  # A4 portrait


def add_page_number(fig, number):
    fig.text(0.92, 0.025, str(number), ha="right", va="bottom", fontsize=8, color=GRAY)
    fig.text(0.08, 0.025, "DFXISP 연구계획서", ha="left", va="bottom", fontsize=8, color=GRAY)


def page_title(fig, title, subtitle=None):
    fig.text(0.08, 0.955, title, fontsize=19, fontproperties=font_manager.FontProperties(fname=FONT_BOLD), color=NAVY, va="top")
    fig.add_artist(plt.Line2D([0.08, 0.92], [0.925, 0.925], color=BLUE, lw=2))
    if subtitle:
        fig.text(0.08, 0.905, subtitle, fontsize=9.5, color=GRAY, va="top")


def wrap(text, width=58):
    out = []
    for para in text.split("\n"):
        if not para.strip():
            out.append("")
        else:
            out.extend(textwrap.wrap(para, width=width, break_long_words=False, break_on_hyphens=False))
    return "\n".join(out)


def body(fig, text, x=0.09, y=0.88, width=62, size=10.5, color="#202830", linespacing=1.55, va="top"):
    fig.text(x, y, wrap(text, width), fontsize=size, color=color, va=va, linespacing=linespacing)


def bullets(fig, items, x=0.10, y=0.84, width=56, size=10.3, gap=0.052, color="#202830"):
    cy = y
    for item in items:
        lines = textwrap.wrap(item, width=width, break_long_words=False, break_on_hyphens=False)
        fig.text(x, cy, "•", fontsize=size + 2, color=BLUE, va="top")
        fig.text(x + 0.025, cy, "\n".join(lines), fontsize=size, color=color, va="top", linespacing=1.45)
        cy -= gap * max(1, len(lines))
    return cy


def callout(fig, title, text, x=0.09, y=0.18, w=0.82, h=0.12, color=BLUE):
    patch = FancyBboxPatch((x, y), w, h, transform=fig.transFigure,
                           boxstyle="round,pad=0.012,rounding_size=0.012",
                           facecolor=LIGHT, edgecolor=color, linewidth=1.2)
    fig.add_artist(patch)
    fig.text(x + 0.02, y + h - 0.025, title, fontsize=10.5, color=color,
             fontproperties=font_manager.FontProperties(fname=FONT_BOLD), va="top")
    fig.text(x + 0.02, y + h - 0.055, wrap(text, 70), fontsize=9.2, color="#26323B", va="top", linespacing=1.35)


def image_page(pdf, num, title, path, caption, subtitle=None):
    fig = plt.figure(figsize=PAGE)
    page_title(fig, title, subtitle)
    ax = fig.add_axes([0.08, 0.20, 0.84, 0.66])
    img = Image.open(path)
    ax.imshow(img)
    ax.axis("off")
    fig.text(0.09, 0.16, wrap(caption, 90), fontsize=9.2, color="#303A43", va="top", linespacing=1.4)
    add_page_number(fig, num)
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def table_page(pdf, num, title, columns, rows, widths=None, subtitle=None, note=None, fontsize=8.5):
    fig = plt.figure(figsize=PAGE)
    page_title(fig, title, subtitle)
    ax = fig.add_axes([0.07, 0.12, 0.86, 0.76])
    ax.axis("off")
    tbl = ax.table(cellText=rows, colLabels=columns, loc="upper center", cellLoc="left", colLoc="center", colWidths=widths)
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(fontsize)
    tbl.scale(1, 2.0)
    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor("#B9C6D2")
        cell.set_linewidth(0.6)
        if r == 0:
            cell.set_facecolor(NAVY)
            cell.get_text().set_color("white")
            cell.get_text().set_fontproperties(font_manager.FontProperties(fname=FONT_BOLD, size=fontsize))
        elif r % 2 == 0:
            cell.set_facecolor("#F5F8FB")
    if note:
        fig.text(0.08, 0.08, wrap(note, 92), fontsize=8.7, color=GRAY, va="top")
    add_page_number(fig, num)
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def architecture_page(pdf, num):
    fig = plt.figure(figsize=PAGE)
    page_title(fig, "6. Proposed Idea — DFXISP 전체 구조", "Static shell에는 ISP 데이터패스가 없고, RP에는 한 번에 하나의 전체 ISP만 상주")
    ax = fig.add_axes([0.05, 0.13, 0.90, 0.74])
    ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")

    def box(x, y, w, h, label, fc, ec=NAVY, fs=9):
        p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05,rounding_size=0.08", fc=fc, ec=ec, lw=1.4)
        ax.add_patch(p); ax.text(x+w/2, y+h/2, label, ha="center", va="center", fontsize=fs, linespacing=1.4)
    def arrow(x1, y1, x2, y2, color=NAVY):
        ax.add_patch(FancyArrowPatch((x1,y1),(x2,y2), arrowstyle="-|>", mutation_scale=12, color=color, lw=1.5))

    box(0.2, 4.2, 1.5, 1.2, "Real RAW\nBayer", "#FFF3D9")
    box(2.0, 6.5, 2.0, 1.2, "RAW checker\ndark16 ratio", LIGHT)
    box(4.4, 6.5, 2.1, 1.2, "Schmitt FSM\n64% enter / 60% exit", LIGHT)
    box(6.9, 6.5, 2.1, 1.2, "DFX Controller\nPR trigger/ack", LIGHT)
    ax.add_patch(FancyBboxPatch((1.8, 5.9), 7.5, 2.4, boxstyle="round,pad=0.08", fc="none", ec=BLUE, lw=2, ls="--"))
    ax.text(2.0, 8.45, "STATIC REGION", color=BLUE, fontsize=11, fontproperties=font_manager.FontProperties(fname=FONT_BOLD))

    ax.add_patch(FancyBboxPatch((2.2, 1.1), 6.6, 3.7, boxstyle="round,pad=0.08", fc="#F8F6FF", ec="#7157A8", lw=2))
    ax.text(2.4, 4.95, "RECONFIGURABLE PARTITION — mutually exclusive", color="#7157A8", fontsize=10.5,
            fontproperties=font_manager.FontProperties(fname=FONT_BOLD))
    box(2.6, 2.7, 5.8, 1.3, "RM_NORMAL\ndemosaic → BLC → AWB/CCM → gain 1.25× → gamma", "#E8F6EC", GREEN)
    box(2.6, 1.35, 5.8, 1.1, "RM_LOW_LIGHT\n2×2 binning-demosaic → BLC → AWB/CCM → gain 2.0× → gamma", "#FFF0E5", ORANGE)
    box(8.7, 3.0, 1.1, 1.2, "RGB32\n→ DPU", "#EAF2FF")
    arrow(1.7,4.8,2.0,7.1); arrow(4.0,7.1,4.4,7.1); arrow(6.5,7.1,6.9,7.1)
    arrow(8.0,6.5,6.8,4.8, RED); arrow(8.4,3.55,8.7,3.55)
    ax.text(7.25, 5.55, "partial bitstream\nscene-level swap", color=RED, fontsize=8.5, ha="center")
    fig.text(0.09, 0.08, "핵심: 파라미터만 바꾸는 것이 아니라 demosaic부터 gamma까지의 전체 구조를 교체한다. checker·mode state·DFX 제어는 항상 static에 남는다.", fontsize=9, color=GRAY)
    add_page_number(fig, num); pdf.savefig(fig, bbox_inches="tight"); plt.close(fig)


def resource_chart_page(pdf, num):
    fig = plt.figure(figsize=PAGE)
    page_title(fig, "2. Problem — 적응성의 하드웨어 비용", "동일 part·wrapper·OOC+DCP flow로 구현한 post-route 비교")
    ax = fig.add_axes([0.13, 0.44, 0.76, 0.40])
    labels = ["Arm1\nStatic normal", "Arm2\nAlways-on adaptive", "Arm3\nDFX normal", "Arm3\nDFX low-light"]
    vals = [3363, 4768, 3363, 2344]
    colors = [GRAY, RED, BLUE, CYAN]
    bars = ax.bar(labels, vals, color=colors, width=0.62)
    ax.set_ylabel("CLB LUT (post-route)"); ax.set_ylim(0, 5400); ax.grid(axis="y", alpha=.25)
    for b, v in zip(bars, vals): ax.text(b.get_x()+b.get_width()/2, v+90, f"{v:,}", ha="center", fontsize=10)
    ax.annotate("-29.5%", xy=(2,3363), xytext=(1.35,4050), arrowprops=dict(arrowstyle="->", color=BLUE), color=BLUE, fontsize=11)
    ax.annotate("-50.8%", xy=(3,2344), xytext=(2.45,3200), arrowprops=dict(arrowstyle="->", color=CYAN), color=CYAN, fontsize=11)
    bullets(fig, [
        "정적 normal ISP에 적응성을 추가하면 3,363→4,768 LUT로 41.8% 증가한다.",
        "DFX는 두 전체 ISP를 동시에 두지 않고 현재 필요한 RM만 RP에 적재한다.",
        "따라서 always-on 대비 normal mode 29.5%, low-light mode 50.8%의 LUT를 절감한다.",
        "현재 수치는 fabric-only post-route 실측이다. 절대 전력과 실제 PR latency는 ZCU104 보드 실측이 남아 있다."
    ], y=0.34, gap=0.043, width=65, size=9.7)
    add_page_number(fig, num); pdf.savefig(fig, bbox_inches="tight"); plt.close(fig)


def schedule_page(pdf, num):
    fig = plt.figure(figsize=PAGE)
    page_title(fig, "8. Expected Contribution & Schedule", "완료된 근거를 보존하면서 보드 실증으로 연구를 마감하는 8주 계획")
    ax = fig.add_axes([0.09, 0.18, 0.82, 0.62]); ax.set_xlim(0,8); ax.set_ylim(0,8); ax.axis("off")
    tasks = [
        ("사양·실험 protocol 동결",0,1,GREEN),
        ("ZCU104 Block Design / AXI / DDR",1,2,BLUE),
        ("ICAPE3·DFX Controller 통합",2,3,BLUE),
        ("drain·ap_idle·warm-up FSM",3,4,ORANGE),
        ("PR latency·switch 안정성",4,5,ORANGE),
        ("Arm1/2/3 전력·energy/frame",5,6,RED),
        ("RAW→ISP→DPU mAP 재측정",6,7,"#7157A8"),
        ("통계·figure·논문 정리",7,8,NAVY),
    ]
    for i,(name,s,e,c) in enumerate(tasks):
        y=7-i
        ax.text(-0.1,y+0.25,name,ha="right",va="center",fontsize=8.5)
        ax.add_patch(FancyBboxPatch((s,y),e-s,0.5,boxstyle="round,pad=0.02",fc=c,ec="none",alpha=.88))
    for w in range(8):
        ax.text(w+.5,7.85,f"W{w+1}",ha="center",fontsize=9,color=GRAY)
        ax.axvline(w,0,.93,color="#D7DEE5",lw=.6,zorder=0)
    callout(fig,"완료 기준","보드에서 세 arm의 동일 입력·동일 FPS 전력과 trigger-to-done PR latency를 확보하고, 실제 RAW→DPU 검출 결과가 SW 평가의 조건별 우위와 일치해야 한다.",y=0.07,h=0.095)
    add_page_number(fig,num); pdf.savefig(fig,bbox_inches="tight"); plt.close(fig)


def build():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(OUT) as pdf:
        n = 1
        # Cover
        fig = plt.figure(figsize=PAGE)
        fig.add_artist(FancyBboxPatch((0,0.72),1,0.28,transform=fig.transFigure,boxstyle="square,pad=0",fc=NAVY,ec="none"))
        fig.text(.08,.87,"DFXISP",fontsize=36,color="white",fontproperties=font_manager.FontProperties(fname=FONT_BOLD))
        fig.text(.08,.79,"조도 적응형 FPGA AI-ISP를 위한\nDynamic Function eXchange 연구계획서",fontsize=20,color="white",linespacing=1.45)
        fig.text(.08,.62,"Research Proposal",fontsize=13,color=BLUE,fontproperties=font_manager.FontProperties(fname=FONT_BOLD))
        fig.text(.08,.56,"대상 플랫폼  AMD Zynq UltraScale+ ZCU104\n입력/과업       Real RAW Bayer → ISP → Object Detection\n핵심 질문       정확도를 유지·개선하면서 미사용 ISP 자원을 회수할 수 있는가?",fontsize=11,color="#25313B",linespacing=1.8)
        callout(fig,"현재 증거 수준","SW 검출 평가, HLS C/RTL co-simulation, Vivado DFX 구현, pr_verify, partial bitstream, 3-arm post-route 자원 비교 완료. 보드 전력·실제 PR latency·DPU end-to-end는 계획 단계.",y=.25,h=.14)
        fig.text(.08,.10,"작성 기준: 저장소 최신 결과 2026-08-14 · 문서 작성 2026-08-18",fontsize=9,color=GRAY)
        pdf.savefig(fig,bbox_inches="tight"); plt.close(fig); n+=1

        # Executive summary
        fig=plt.figure(figsize=PAGE); page_title(fig,"Executive Summary")
        body(fig,"DFXISP는 밝은 장면과 저조도 장면에 서로 다른 전체 ISP 파이프라인이 필요하다는 알고리즘적 관찰을, FPGA의 Dynamic Function eXchange를 이용한 물리적 자원 공유로 연결한다.",y=.87,width=65,size=11)
        bullets(fig,[
            "Normal RM과 Low-light RM은 demosaic→BLC→AWB/CCM→gain→gamma 전체를 각각 소유하며, 한 시점에는 하나만 Reconfigurable Partition에 상주한다.",
            "RAW dark-pixel ratio와 Schmitt hysteresis가 장면을 판정하고, fabric의 DFX Controller가 PS 없는 trigger 경로를 제공한다.",
            "100장 교차검증에서 주간 default ISP는 YOLOv8n mAP 0.3921→0.4082, 야간 low-light ISP는 0.1260→0.1447로 개선됐다. SSDLite에서도 같은 방향이 확인됐다.",
            "Post-route에서 always-on adaptive는 4,768 LUT, DFX는 normal 3,363 LUT 및 low-light 2,344 LUT다. 각각 29.5%, 50.8% 절감이다.",
            "연구의 마지막 검증은 ZCU104의 실제 PR latency, 전력/energy-frame, RAW→DPU end-to-end mAP다."
        ],y=.76,gap=.073,width=63,size=10.1)
        callout(fig,"주장 규칙","현재는 정확도와 post-route 자원 절감만 확정 결과로 주장한다. 전력 절감과 보드 전환 지연은 실측 전까지 연구 가설 또는 예상 기여로 표기한다.",y=.10,h=.11,color=RED)
        add_page_number(fig,n); pdf.savefig(fig,bbox_inches="tight"); plt.close(fig); n+=1

        # Background 1
        fig=plt.figure(figsize=PAGE); page_title(fig,"1. Research Background — 왜 AI-ISP인가?")
        body(fig,"카메라 센서의 Bayer RAW는 바로 객체 검출기에 투입하기 어렵다. BLC는 센서 offset을 제거하고, demosaic는 CFA를 RGB로 복원하며, AWB/CCM은 조명과 센서 색응답을 보정하고, gain/gamma는 제한된 출력 범위에 신호를 배치한다. 이 과정은 화질뿐 아니라 검출기의 입력 분포를 결정한다.",y=.88,width=66)
        bullets(fig,[
            "저조도의 본질은 단순한 밝기 감소가 아니라 photon shot noise와 read noise로 인한 SNR 저하다. RAW noise는 보통 Var[z|y]=a·y+b의 Poisson–Gaussian 모델로 근사한다.",
            "Digital gain은 신호와 잡음을 함께 키우므로 SNR 자체를 회복하지 못한다. BLC 오차와 clipping은 후단 gain 및 gamma에서 확대될 수 있다.",
            "2×2 binning은 이상적인 독립 noise 가정에서 SNR을 높이지만, 출력 폭·높이를 절반으로 줄여 객체의 픽셀 면적을 1/4로 만든다.",
            "따라서 PSNR/SSIM만으로 ISP를 선택할 수 없으며, 동일 detector와 split에서 mAP·AP-small·recall을 직접 평가해야 한다."
        ],y=.70,gap=.066,width=62,size=10)
        callout(fig,"연구의 출발점","사람이 보기 좋은 ISP와 기계가 인식하기 좋은 ISP는 다를 수 있으며, 최적 ISP 구조와 파라미터는 조도 및 센서 조건에 의존한다.",y=.11,h=.105)
        add_page_number(fig,n); pdf.savefig(fig,bbox_inches="tight"); plt.close(fig); n+=1

        # Background 2
        fig=plt.figure(figsize=PAGE); page_title(fig,"1. Research Background — 왜 DFX인가?")
        body(fig,"FPGA는 streaming ISP를 낮은 지연과 높은 병렬성으로 구현하기 적합하지만, 일반적인 적응형 설계는 후보 모듈을 모두 합성한 뒤 mux 또는 register로 선택한다. 실행하지 않는 모듈도 실리콘 자원을 점유한다.",y=.88,width=65)
        bullets(fig,[
            "Parameter adaptation: gain, gamma, AWB/CCM 계수처럼 동일 구조 안의 값만 변경한다. 빠르지만 구조 자체를 바꾸지는 못한다.",
            "Conditional execution: 소프트웨어가 ISP module 또는 pipeline 순서를 선택한다. 연산량은 줄어도 FPGA에 합성된 면적은 남을 수 있다.",
            "Static heterogeneous acceleration: ISP와 neural network의 일을 나누거나 PE를 공유한다. 효율적이지만 설계 시 정한 구조가 런타임에 고정된다.",
            "Dynamic Function eXchange: static shell을 유지한 채 RP의 bitstream을 교체한다. 상호배타적인 전체 ISP가 같은 물리 자원을 시간적으로 공유한다."
        ],y=.70,gap=.073,width=62,size=10)
        callout(fig,"DFXISP의 위치","DynamicISP/AdaptiveISP가 제시한 장면 적응을 HISP/Hybrid VPU의 FPGA 효율 문제와 연결하고, 미사용 ISP의 물리적 면적까지 회수한다.",y=.10,h=.115)
        add_page_number(fig,n); pdf.savefig(fig,bbox_inches="tight"); plt.close(fig); n+=1

        resource_chart_page(pdf,n); n+=1
        image_page(pdf,n,"2. Problem — 조건별 ISP가 실제 검출 성능을 바꾼다",RESULTS/"v2_v1_cross_detector_contrast_2026-08-06.png",
                   "그림 2. v2-v1 검출 지표 변화. 주간 default ISP와 야간 low-light ISP의 개선 방향이 YOLOv8n과 SSDLite-MobileNetV3-Large에서 교차 확인됐다. 단, detector별 score threshold가 달라 scalar precision의 절대값을 detector 사이에서 직접 비교해서는 안 된다.")
        n+=1

        # Related works intro + 5 works
        table_page(pdf,n,"3. Related Work — 연구 지형",["연구","핵심 해결 방식","적응/공유 단위","DFXISP 관점의 공백"],[
            ["Dark-ISP\n(ICCV 2025)","Differentiable linear/nonlinear RAW ISP + Self-Boost","내용별 파라미터","FPGA/PR 자원·지연 미평가"],
            ["DynamicISP\n(ICCV 2023)","이전 프레임 인식 결과로 classical ISP 제어","프레임별 파라미터","회로 구조 고정"],
            ["AdaptiveISP\n(NeurIPS 2024)","DRL로 module·순서·parameter 선택","영상별 pipeline","conditional compute, 물리 면적 상주"],
            ["HISP\n(Electronics 2023)","Traditional ISP + DLISP/DPU 기능 분할","설계 시 이종 분할","static pipeline, IQA 중심"],
            ["Hybrid VPU\n(Electronics 2021)","ISP와 CNN이 hybrid PE array 공유","연산기 공간 공유","장면별 회로 교체 없음"],
            ["DFXISP\n(본 연구)","Checker + scene-level whole-ISP DFX","RP의 시간적 공유","보드 전력·PR latency 실측 필요"],
        ],widths=[.14,.31,.19,.30],fontsize=7.8,note="표 1. 관련 연구는 서로 대체 관계라기보다 다른 계층을 해결한다. DFXISP의 차별점은 task-aware ISP 선택을 실제 FPGA 상주 자원의 변화로 연결하는 것이다.")
        n+=1

        fig=plt.figure(figsize=PAGE); page_title(fig,"3.1 Dark-ISP — 저조도 RAW 검출을 위한 task-driven ISP")
        body(fig,"Guo et al., ‘Dark-ISP: Enhancing RAW Image Processing for Low-Light Object Detection,’ ICCV 2025.",y=.88,width=70,size=10,color=BLUE)
        bullets(fig,[
            "Bayer RAW를 직접 처리하는 lightweight self-adaptive ISP plugin을 제안한다.",
            "전통 ISP를 sensor calibration 성격의 linear sub-module과 tone mapping 성격의 nonlinear sub-module로 분해한다.",
            "두 부분을 differentiable component로 만들고 detection loss로 end-to-end 최적화한다.",
            "Content-aware adaptation과 physics-informed prior를 사용하며, cascade 구조의 두 부분이 협력하도록 Self-Boost mechanism을 둔다.",
            "세 RAW dataset에서 RGB/RAW 기반 기존 검출 방법보다 우수한 결과를 작은 parameter 수로 보고한다."
        ],y=.78,gap=.061,width=62,size=9.9)
        callout(fig,"DFXISP와의 관계","Dark-ISP는 ‘저조도에서 어떤 RAW 처리가 검출에 유리한가’를 해결한다. DFXISP는 normal/low-light 전체 pipeline의 런타임 상주 방식과 FPGA 비용을 해결한다. Dark-ISP는 FPGA resource, partial bitstream, PR latency와 전력을 평가하지 않는다.",y=.10,h=.15)
        add_page_number(fig,n); pdf.savefig(fig,bbox_inches="tight"); plt.close(fig); n+=1

        fig=plt.figure(figsize=PAGE); page_title(fig,"3.2 DynamicISP — 인식 피드백 기반 프레임별 파라미터 제어")
        body(fig,"Yoshimura et al., ‘DynamicISP: Dynamically Controlled Image Signal Processor for Image Recognition,’ ICCV 2023, pp. 12866–12876.",y=.88,width=70,size=10,color=BLUE)
        bullets(fig,[
            "여러 classical ISP function과 controller를 결합한다.",
            "이전 프레임의 recognition result를 사용해 다음 프레임의 ISP parameter를 제어한다.",
            "수동 ISP tuning의 sub-optimality와 DNN ISP의 높은 edge computation cost 사이를 절충한다.",
            "Single-category와 multi-category object detection에서 낮은 연산 비용으로 높은 정확도를 보고한다.",
            "장면별 ISP adaptation이 recognition accuracy를 높일 수 있다는 DFXISP의 알고리즘 가설을 직접 뒷받침한다."
        ],y=.76,gap=.062,width=62,size=9.9)
        callout(fig,"한계와 차별점","동일한 classical ISP 구조에서 parameter를 바꾸므로 demosaic와 binning-demosaic처럼 데이터패스 구조가 다른 pipeline을 교체하기 어렵다. 미사용 hardware resource도 회수하지 않는다.",y=.11,h=.13)
        add_page_number(fig,n); pdf.savefig(fig,bbox_inches="tight"); plt.close(fig); n+=1

        fig=plt.figure(figsize=PAGE); page_title(fig,"3.3 AdaptiveISP — pipeline 구조와 파라미터의 공동 선택")
        body(fig,"Wang et al., ‘AdaptiveISP: Learning an Adaptive Image Signal Processor for Object Detection,’ NeurIPS 2024.",y=.88,width=70,size=10,color=BLUE)
        bullets(fig,[
            "Deep reinforcement learning을 이용해 ISP module, 실행 순서, parameter를 객체 검출 목적에 맞게 공동 선택한다.",
            "대부분의 입력에는 소수 module만 필요하고 일부 어려운 입력에만 더 많은 처리가 필요하다는 관찰을 이용한다.",
            "고정 pipeline보다 dynamic scene에 강하며 detection performance와 computational cost의 trade-off를 관리한다.",
            "DFXISP의 normal/low-light/adaptive 3-arm 평가와 ‘필요한 것만 실행한다’는 설계 철학에 가장 가까운 software baseline이다."
        ],y=.76,gap=.071,width=62,size=10)
        callout(fig,"한계와 차별점","Conditional execution은 FLOPs를 줄이지만 FPGA에 이미 합성된 LUT·BRAM·DSP의 물리 면적을 제거하지 않을 수 있다. 보상함수에도 partial-bitstream 크기, drain, frame stall, PR energy 같은 DFX 비용이 없다.",y=.11,h=.14)
        add_page_number(fig,n); pdf.savefig(fig,bbox_inches="tight"); plt.close(fig); n+=1

        fig=plt.figure(figsize=PAGE); page_title(fig,"3.4 HISP — Traditional ISP와 DLISP의 FPGA 이종 결합")
        body(fig,"‘HISP: Heterogeneous Image Signal Processor Pipeline Combining Traditional and Deep Learning Algorithms Implemented on FPGA,’ Electronics 2023, 12(16), 3525.",y=.88,width=72,size=9.8,color=BLUE)
        bullets(fig,[
            "Deep-learning ISP가 extreme low-light의 복잡한 RAW 처리를 맡고, traditional streaming module이 AWB와 edge enhancement 등 저비용 후처리를 맡는다.",
            "UNet 계열 처리를 FPGA DPU로 가속해 ARM CPU의 7,675 ms를 523.28 ms로 줄였다고 보고한다(14.67×).",
            "DPU+AWB+EE를 최적 조합으로 선택했으며 전체 HISP latency 524.93 ms, total power 12.6 W를 보고한다.",
            "전통 ISP와 DLISP의 장단점을 기능 분할하고 FPGA에 통합했다는 점에서 DFXISP의 hardware-side 선행연구다."
        ],y=.73,gap=.074,width=63,size=9.7)
        callout(fig,"한계와 차별점","선택된 HISP 조합은 static pipeline이며 조도에 따라 전체 pipeline을 runtime 교체하지 않는다. 평가는 BRISQUE·PIQE·NIQE 등 IQA 중심이고, detector mAP와 DFX 자원 회수는 다루지 않는다.",y=.10,h=.14)
        add_page_number(fig,n); pdf.savefig(fig,bbox_inches="tight"); plt.close(fig); n+=1

        fig=plt.figure(figsize=PAGE); page_title(fig,"3.5 Hybrid VPU — ISP와 CNN을 위한 공유 PE array")
        body(fig,"Liu and Song, ‘A Hybrid Vision Processing Unit with a Pipelined Workflow for Convolutional Neural Network Accelerating and Image Signal Processing,’ Electronics 2021, 10(23), 2989.",y=.88,width=72,size=9.8,color=BLUE)
        bullets(fig,[
            "별도 ISP와 CNN accelerator 사이의 pixel transfer와 redundant hardware 문제를 해결한다.",
            "Hybrid processing-element array가 ISP와 CNN operation을 모두 처리하며, MAC과 on-chip memory를 공간적으로 공유한다.",
            "Pipelined workflow로 sensor-to-recognition 흐름을 연결하고 다양한 CNN operation을 지원한다.",
            "FPGA 200 MHz에서 평균 MAC utilization 94% 이상, 163.2 GOPS를 보고한다.",
            "ISP와 recognition을 하나의 효율적 하드웨어로 묶는다는 점에서 end-to-end DFXISP의 구현 방향과 맞닿는다."
        ],y=.73,gap=.064,width=63,size=9.8)
        callout(fig,"한계와 차별점","Hybrid VPU는 동일 PE array에 연산을 mapping하는 공간적 공유다. DFXISP는 mode-specific dedicated ISP netlist가 동일 RP를 시간적으로 공유한다. Hybrid VPU는 scene-level circuit swap이나 PR 비용을 평가하지 않는다.",y=.10,h=.14)
        add_page_number(fig,n); pdf.savefig(fig,bbox_inches="tight"); plt.close(fig); n+=1

        # Gap
        fig=plt.figure(figsize=PAGE); page_title(fig,"4. Limitation / Research Gap")
        body(fig,"기존 연구를 계층별로 보면 각각 강점은 분명하지만, 알고리즘의 장면 적응이 실제 FPGA 상주 자원의 변화로 이어지지 않는다.",y=.88,width=66,size=11)
        bullets(fig,[
            "Dark-ISP는 저조도 RAW 처리의 task-aware 알고리즘을 제공하지만 normal/dark mode의 하드웨어 공존 비용을 다루지 않는다.",
            "DynamicISP는 parameter adaptation을, AdaptiveISP는 pipeline selection을 해결하지만 둘 다 FPGA partial reconfiguration의 비용 모델이 없다.",
            "HISP는 traditional/DLISP의 정적 이종 결합을, Hybrid VPU는 ISP/CNN PE 공유를 해결하지만 장면별 전체 ISP 교체는 제공하지 않는다.",
            "기존 정확도 연구는 mAP는 보고해도 LUT·BRAM·DSP·power·PR latency를 함께 비교하지 않으며, 하드웨어 연구는 IQA/throughput 중심이라 detection task와 분리된다.",
            "따라서 real RAW scene 판단→whole-ISP 선택→DFX trigger→미사용 자원 회수→detector 평가를 하나의 시스템에서 검증할 필요가 있다."
        ],y=.72,gap=.065,width=62,size=9.8)
        callout(fig,"Research gap","Task-aware adaptive ISP와 FPGA DFX 사이의 단절: ‘무엇을 선택할 것인가’는 연구됐지만, ‘선택하지 않은 전체 ISP 회로를 실제로 제거하고 그 정확도·면적·전력·전환비용을 함께 검증하는가’는 충분히 다뤄지지 않았다.",y=.08,h=.16,color=RED)
        add_page_number(fig,n); pdf.savefig(fig,bbox_inches="tight"); plt.close(fig); n+=1

        # RQ
        fig=plt.figure(figsize=PAGE); page_title(fig,"5. Research Question / Objective")
        callout(fig,"Main RQ","조도에 특화된 전체 ISP를 장면별로 선택하고 FPGA DFX로 교체하면, 객체 검출 정확도를 유지 또는 개선하면서 always-on adaptive ISP보다 FPGA 자원과 전력을 줄일 수 있는가?",y=.73,h=.15,color=BLUE)
        bullets(fig,[
            "RQ1 — 필요성: Normal ISP와 low-light ISP가 각각 자기 조도 조건에서 상대 ISP보다 높은 mAP를 제공하는가?",
            "RQ2 — 선택: 저비용 RAW dark-ratio와 hysteresis로 적합한 ISP를 안정적으로 선택할 수 있는가?",
            "RQ3 — 자원: DFX가 두 pipeline 동시 상주 대비 LUT·FF·BRAM·DSP를 얼마나 줄이는가?",
            "RQ4 — 실시간성: drain+configuration+warm-up 지연이 scene-level 전환에서 허용 가능한가?",
            "RQ5 — 에너지: 동일 FPS와 detector 조건에서 board power 및 energy/frame이 감소하는가?",
            "RQ6 — 일반화: 조건별 우위가 YOLOv8n뿐 아니라 SSDLite 또는 YOLOv8s에서도 유지되는가?"
        ],y=.62,gap=.052,width=64,size=9.7)
        add_page_number(fig,n); pdf.savefig(fig,bbox_inches="tight"); plt.close(fig); n+=1

        architecture_page(pdf,n); n+=1
        image_page(pdf,n,"6. Proposed Idea — Checker와 hysteresis",RESULTS/"checker_validation_2026-08-06"/"checker_band_comparison_2026-08-06.png",
                   "그림 4. 중심 threshold 62% 주위에서 enter 64%/exit 60%의 Schmitt band를 사용한다. 목적은 임계 부근의 noise로 인한 mode flapping과 불필요한 PR을 억제하는 것이다. mode state는 static fabric이 소유한다.")
        n+=1
        image_page(pdf,n,"6. Proposed Idea — HLS/RTL 검증 상태",RESULTS/"cosim-pass-summary-2026-08-14.png",
                   "그림 5. RM과 checker의 C/RTL co-simulation 요약. Python/C++ golden, C-simulation, RTL co-simulation을 단계적으로 사용해 arithmetic과 interface를 고정한다. DFX 구현에서는 두 RM의 110-port signature 일치 및 pr_verify PASS를 별도로 확인했다.")
        n+=1

        # Evaluation plan
        table_page(pdf,n,"7. Evaluation Plan — 실험 arm과 가설",["Arm","구성","검증 목적","주요 비교"],[
            ["Arm1","Static RM_NORMAL","비적응 최소 HW 기준","정확도·자원·전력 기준점"],
            ["Arm2","RM_NORMAL+RM_LOW_LIGHT 동시 상주, register/mux 선택","DFX 없는 적응형 baseline","적응성의 면적·전력 비용"],
            ["Arm3","Static checker/controller + 하나의 DFX RP","제안 시스템","Arm2 대비 자원·전력 절감"],
            ["Forced normal","모든 입력에 normal ISP","조건 불일치 손실","LOD에서 low-light와 비교"],
            ["Forced low-light","모든 입력에 low-light ISP","조건 불일치 손실","PASCAL에서 normal과 비교"],
            ["Adaptive","Checker가 자동 선택","전체 정책의 실효성","oracle 및 forced arm과 비교"],
        ],widths=[.14,.30,.25,.25],fontsize=8.1,note="색보정되지 않은 none 출력은 배포 가능한 ISP 출력이 아니므로 primary baseline에서 제외한다. 정확도 비교는 normal/low-light/adaptive를 중심으로 수행한다.")
        n+=1

        table_page(pdf,n,"7. Evaluation Plan — Dataset, detector, metric",["축","구성","측정값"],[
            ["Bright RAW","PASCAL RAW / PASCAL split","Normal 우위 및 checker false-enter"],
            ["Low-light RAW","LOD/SonyNOD real RAW","Low-light 우위 및 checker miss"],
            ["Detector","YOLOv8n, SSDLite-MobileNetV3-Large; 선택 YOLOv8s","모델 간 방향 일치"],
            ["Task metric","COCO mAP@[.5:.95], mAP@50, precision, recall","동일 split·동일 inference setting"],
            ["Scale metric","AP-small/medium/large","2×2 binning의 small-object 비용"],
            ["Checker","confusion matrix, balanced accuracy, Youden J","false enter/exit, switch count"],
            ["Hardware","LUT/FF/BRAM/DSP, WNS/Fmax, FPS","동일 part·clock·wrapper·flow"],
            ["DFX/energy","bitstream bytes, trigger-to-done, ICAP BW, W, J/frame","보드 반복측정 및 CI"],
        ],widths=[.16,.42,.36],fontsize=8.1,note="Detector 간 scalar precision/recall은 기본 score threshold가 다르므로 절대값을 직접 비교하지 않고, 각 detector 내부의 arm 차이를 해석한다.")
        n+=1

        image_page(pdf,n,"7. Evaluation Plan — 현재 검출 baseline",RESULTS/"map_precision_recall_split_nod_yolov8n_2026-08-06.png",
                   "그림 6. 야간 split의 YOLOv8n 결과. normal 0.1260, 기존 lowlight 0.1410, 배포 lowlight_isp 0.1447 mAP@[.5:.95]이다. 최종 보드 실험에서는 동일 RAW와 detector를 사용해 HW 출력이 이 순서를 재현하는지 검증한다.")
        n+=1
        image_page(pdf,n,"7. Evaluation Plan — HLS 자원 및 timing gate",RESULTS/"csynth-resources-2026-08-14.png",
                   "그림 7. 최신 HLS synthesis 자원 요약. HLS 추정치는 기능/회귀 gate로 사용하고, 논문의 arm 간 면적 결론은 동일 조건 post-route 수치를 사용한다. HLS estimate와 Vivado mapping 수치를 혼합해 빼지 않는다.")
        n+=1

        # Expected contributions
        fig=plt.figure(figsize=PAGE); page_title(fig,"8. Expected Contribution")
        bullets(fig,[
            "C1 — Architecture: static shell과 하나의 RP로 구성된 scene-adaptive whole-ISP DFX 구조를 제시한다.",
            "C2 — Control: RAW dark-ratio, Schmitt hysteresis, drain/idle handshake, DFX Controller를 연결한 PS-free 판단·trigger 경로를 구현한다.",
            "C3 — Task evidence: bright/low-light real RAW에서 condition-specific ISP의 필요성을 YOLO와 SSDLite로 교차 검증한다.",
            "C4 — Resource evidence: 동일 post-route 축에서 always-on 대비 normal 29.5%, low-light 50.8% LUT 절감을 보인다.",
            "C5 — Evaluation methodology: mAP·AP-small·checker error와 LUT·timing·PR latency·energy/frame을 하나의 protocol로 결합한다.",
            "C6 — Extensibility: denoise, HDR, task-specific tone mapping 등 추가 RM을 같은 static interface에 삽입할 수 있는 기반을 제공한다."
        ],y=.84,gap=.071,width=64,size=10)
        callout(fig,"성공 조건","보드 결과가 (1) 조건별 정확도 우위를 보존하고, (2) Arm2보다 낮은 상주 자원과 energy/frame을 보이며, (3) PR 지연을 포함해 scene-level switching이 안정적으로 동작할 때 전체 기여가 완성된다.",y=.10,h=.14,color=GREEN)
        add_page_number(fig,n); pdf.savefig(fig,bbox_inches="tight"); plt.close(fig); n+=1

        schedule_page(pdf,n); n+=1

        # Risks
        table_page(pdf,n,"Risk, Limitation, Mitigation",["위험/한계","영향","대응"],[
            ["PR latency가 frame budget 초과","프레임별 전환 불가","scene-level 전환, minimum dwell, drain, invalid window"],
            ["2×2 binning의 small-object 손실","저조도에서도 mAP 하락 가능","AP-small 분리, full-resolution ablation, 조도별 gate"],
            ["고정 dark threshold의 sensor 의존성","다른 gain/ISO에서 오판","sensor metadata 층화, calibration, threshold register화"],
            ["SW와 HW RAW 규약 차이","mAP 결과 재현 실패","CFA/bit-depth/black level 명시, golden bit-exact, HW output cache"],
            ["DFX power 이득이 작음","핵심 주장 약화","동일 FPS/clock의 board rail 측정, static/dynamic 분리, energy/frame"],
            ["Partial bitstream 1.38 MB","전환 시간·DDR traffic 증가","pblock 축소 재검토, ICAP BW 실측, swap 빈도 제한"],
            ["Detector threshold confound","precision 해석 왜곡","COCO mAP primary, detector 내부 arm delta, PR curve 병기"],
        ],widths=[.27,.28,.39],fontsize=8.2,note="현재 partial bitstream은 1,447,424 bytes다. 이론적 전환 지연은 가정에 민감하므로 최종 논문에서는 보드 trigger-to-done 실측을 우선한다.")
        n+=1

        # References
        fig=plt.figure(figsize=PAGE); page_title(fig,"References & Evidence")
        refs=[
            "[1] Guo et al., Dark-ISP: Enhancing RAW Image Processing for Low-Light Object Detection, ICCV 2025. https://arxiv.org/abs/2509.09183",
            "[2] Yoshimura et al., DynamicISP: Dynamically Controlled Image Signal Processor for Image Recognition, ICCV 2023. https://arxiv.org/abs/2211.01146",
            "[3] Wang et al., AdaptiveISP: Learning an Adaptive Image Signal Processor for Object Detection, NeurIPS 2024. https://arxiv.org/abs/2410.22939",
            "[4] HISP: Heterogeneous Image Signal Processor Pipeline Combining Traditional and Deep Learning Algorithms Implemented on FPGA, Electronics 2023, 12(16), 3525. https://doi.org/10.3390/electronics12163525",
            "[5] Liu and Song, A Hybrid Vision Processing Unit with a Pipelined Workflow for CNN Accelerating and ISP, Electronics 2021, 10(23), 2989. https://doi.org/10.3390/electronics10232989",
            "[6] Foi et al., Practical Poissonian-Gaussian Noise Modeling and Fitting for Single-Image Raw-Data, IEEE TIP 2008.",
            "[7] Hong et al., Crafting Object Detection in Very Low Light, BMVC 2021.",
            "[8] AMD, Dynamic Function eXchange / DFX Controller and Vitis Vision documentation.",
            "[9] Local evidence: README.md, Background.md, SPEC.md, ROADMAP.md.",
            "[10] Local measurements: mAP-precision-recall-2026-08-06.md, dfx-reimplementation-2026-08-01.md, checker validation and csynth/cosim reports."
        ]
        bullets(fig,refs,y=.86,gap=.056,width=72,size=8.8)
        callout(fig,"재현성","수치와 그림은 /isppipeline/hls/results의 저장소 산출물을 사용했다. PDF 생성 스크립트도 research_plan/build_research_proposal.py에 함께 보존한다.",y=.07,h=.10)
        add_page_number(fig,n); pdf.savefig(fig,bbox_inches="tight"); plt.close(fig)

    print(OUT)


if __name__ == "__main__":
    build()
