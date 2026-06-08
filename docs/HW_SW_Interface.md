# Hardware / Software Interface Specification

이 문서는 현재 저장소 기준으로 하드웨어/소프트웨어 경계에서 중요한 인터페이스를 정리합니다.

중요한 점은 이 저장소에 두 계층의 인터페이스 정보가 함께 존재한다는 것입니다.

1. 현재 메인라인 알고리즘 기준 인터페이스
   - RGB32 중심
   - Python 골든모델 / HLS 커널 정합 기준
2. 과거 보드 통합 기준 인터페이스
   - ZCU104 DFX 실험에서 실제 사용한 AXI-Lite / DDR 주소 맵
   - 일부는 grayscale / YUYV 시기의 기록

이 문서는 두 정보를 구분해 기록합니다.

---

## 1. 현재 메인라인 데이터 인터페이스

### 1.1 RGB32 패킹 규약

현재 연구 메인라인에서 기준으로 삼는 컬러 스트림 포맷은 아래와 같습니다.

```text
[31:24] = 0x00
[23:16] = B
[15:8]  = G
[7:0]   = R
```

즉, 유효 데이터는 하위 24비트의 BGR 순서이며 상위 8비트는 패딩입니다.

### 1.2 pseudo-RAW Bayer 데이터

pseudo-RAW 데이터셋은 단일 채널 16-bit Bayer PNG를 사용합니다.

- 포맷: RGGB Bayer
- 저장 범위: `uint16`
- 생성 위치: `Dataset/COCO_5000_raw/`, `Dataset/ExDark_5000_raw/`

### 1.3 Python 골든모델 기준 입출력

`isppipeline/unprocess/isp_pipeline.py`는 현재 HW 검증의 기준 모델입니다.

주요 관점:

- 입력은 sRGB 또는 pseudo-RAW 경로로 해석 가능
- 출력 기준은 RGB32
- HW C-Sim / RTL 검증은 이 Python 골든모델과의 픽셀 단위 정합을 목표로 함

---

## 2. 현재 알고리즘 단계별 인터페이스 해석

### 2.1 Baseline 파이프라인

개념적 데이터 흐름:

```text
Bayer16
  -> Bayer8
  -> BLC
  -> Gain
  -> Demosaic
  -> CCM
  -> Gamma
  -> RGB output
```

### 2.2 Proposal 파이프라인

개념적 데이터 흐름:

```text
input
  -> checker
  -> mode selection
  -> normal path or low-light path
  -> ISP
  -> RGB32 output
```

Low-Light 모드에서는 현재 연구 설계상 다음 처리가 핵심입니다.

- 2x2 binning
- gain
- gamma 강화

---

## 3. 보드 통합 기준 레거시 AXI-Lite 주소 맵

아래 주소 맵은 ZCU104 기반 DFX 보드 통합 시 사용했던 기준값입니다.  
이 값은 최신 RGB32 메인라인 전체가 보드에 재통합되었다는 뜻이 아니라, 기존 하드웨어 실험 문서의 기준 주소를 보존하는 것입니다.

| IP Name | Base Address | High Address | 설명 |
|------|------|------|------|
| `AXI_DMA_0` | `0xA000_0000` | `0xA000_FFFF` | DDR <-> ISP 스트리밍 DMA |
| `AXI_GPIO_0` | `0xA001_0000` | `0xA001_FFFF` | PR 상태 모니터링 GPIO |
| `ISP_PIPELINE` | `0xA002_0000` | `0xA002_FFFF` | ISP HLS 커널 제어 영역 |

이 주소는 보드 제어 코드나 옛 RTL/BD 문서와 대조할 때 사용합니다.

---

## 4. DMA 레지스터 오프셋

레거시 ZCU104 통합 기준 DMA 레지스터 주요 오프셋은 아래와 같습니다.

| Offset | Register | 설명 |
|------|------|------|
| `0x00` | `MM2S_CR` | MM2S 제어 |
| `0x04` | `MM2S_SR` | MM2S 상태 |
| `0x18` | `MM2S_SA` | MM2S 소스 주소 |
| `0x28` | `MM2S_LENGTH` | MM2S 전송 바이트 수 |
| `0x30` | `S2MM_CR` | S2MM 제어 |
| `0x34` | `S2MM_SR` | S2MM 상태 |
| `0x48` | `S2MM_DA` | S2MM 목적지 주소 |
| `0x58` | `S2MM_LENGTH` | S2MM 전송 바이트 수 |

### 주의

기존 문서에는 아래와 같은 과거 설정이 함께 등장합니다.

- MM2S 8-bit
- S2MM 16-bit YUYV

이 값은 grayscale / YUYV 시기의 기록입니다.  
현재 메인라인 연구 방향은 RGB32 in/out이므로, 실제 최신 보드 통합을 다시 수행할 때는 DMA 비트폭과 스트림 연결을 RGB32 기준으로 재정의해야 합니다.

---

## 5. ISP HLS 제어 레지스터

레거시 HLS 제어 레지스터 구조는 일반적인 Vitis HLS 커널 형태를 따릅니다.

| Offset | Register | 설명 |
|------|------|------|
| `0x00` | `CTRL` | `ap_start`, `ap_done`, `ap_idle` |
| `0x04` | `GIER` | 글로벌 인터럽트 |
| `0x10+` | scalar args | width, height, 사용자 파라미터 |

실제 scalar argument 순서는 합성 결과에 따라 달라질 수 있으므로, HLS export 결과 헤더와 함께 확인해야 합니다.

---

## 6. DDR 비트스트림 적재 영역

부분 재구성 실험 문서 기준 DDR 레이아웃은 아래와 같습니다.

| Start Address | Size | 용도 |
|------|------|------|
| `0x1000_0000` | 2 MB | Normal partial bitstream |
| `0x1020_0000` | 2 MB | Low-Light partial bitstream |
| `0x1040_0000+` | - | 예비 영역 |

이 레이아웃은 PR Controller가 DDR에서 partial bitstream을 읽어 ICAP로 전달하는 흐름을 전제로 합니다.

---

## 7. 현재 문서 해석 원칙

이 문서를 사용할 때는 아래처럼 구분해야 합니다.

### 현재 기준으로 신뢰할 정보

1. RGB32 패킹 규약
2. pseudo-RAW Bayer 데이터 형식
3. Python 골든모델이 HW 정합 기준이라는 점
4. proposal 파이프라인의 모드 기반 처리 개념

### 역사적 참조로 봐야 할 정보

1. grayscale / YUYV 기반 DMA 폭 설명
2. 기존 RTL/DFX 보드 통합 주소 맵
3. 과거 partial bitstream 파일명이나 세부 로딩 절차

---

## 8. 이후 갱신이 필요한 항목

아래 작업이 완료되면 이 문서를 다시 갱신해야 합니다.

1. RGB32 기준 보드 Block Design 재정합
2. 최신 HLS scalar register map 확정
3. 최신 partial bitstream 적재 경로 확정
4. DPU 직결 경로의 실제 MM2S/S2MM 연결 확정
