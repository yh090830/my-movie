import requests
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ---------------------------------------------------------
# 1. 기본 설정
# ---------------------------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 어제의 박스오피스")

# 한국 시간 기준으로 오늘 날짜를 구합니다.
# 배포 서버가 어느 나라 시간으로 설정되어 있어도 한국 시간을 사용합니다.
KST = ZoneInfo("Asia/Seoul")
today_kst = datetime.now(KST).date()

# "어제" 날짜를 자동으로 계산합니다.
yesterday = today_kst - timedelta(days=1)

# KOBIS API가 요구하는 YYYYMMDD 형식으로 바꿉니다.
target_dt = yesterday.strftime("%Y%m%d")

st.caption(f"조회 날짜: {yesterday.strftime('%Y년 %m월 %d일')} (한국 시간 기준)")


# ---------------------------------------------------------
# 2. KOBIS API 호출 함수
# ---------------------------------------------------------

@st.cache_data(ttl=3600)
def get_box_office(target_dt, api_key):
    """
    KOBIS 일일 박스오피스 API를 호출합니다.

    cache_data의 ttl=3600은 결과를 약 1시간 동안 기억하게 합니다.
    따라서 같은 날짜를 다시 조회해도 매번 API를 호출하지 않습니다.
    """

    url = (
        "https://www.kobis.or.kr/"
        "kobisopenapi/webservice/rest/boxoffice/"
        "searchDailyBoxOfficeList.json"
    )

    params = {
        "key": api_key,
        "targetDt": target_dt,
    }

    # API에 요청합니다.
    response = requests.get(url, params=params, timeout=10)

    # HTTP 상태 코드가 200이 아니면 오류로 처리합니다.
    response.raise_for_status()

    # JSON 응답을 파이썬 객체로 변환합니다.
    data = response.json()

    return data


# ---------------------------------------------------------
# 3. Secrets에서 인증키 읽기
# ---------------------------------------------------------

# Streamlit Cloud의 Secrets에
# KOBIS_KEY = "발급받은 인증키"
# 형태로 등록해 둡니다.
try:
    api_key = st.secrets["KOBIS_KEY"]
except KeyError:
    st.error(
        "KOBIS_KEY를 찾을 수 없습니다. "
        "Streamlit Cloud의 앱 설정 → Secrets에 "
        "`KOBIS_KEY = \"발급받은 인증키\"`가 등록되어 있는지 확인해 주세요."
    )
    st.stop()


# ---------------------------------------------------------
# 4. API 호출 및 오류 처리
# ---------------------------------------------------------

try:
    data = get_box_office(target_dt, api_key)

except requests.exceptions.Timeout:
    st.error(
        "KOBIS API 응답 시간이 초과되었습니다. "
        "잠시 후 다시 시도하거나 KOBIS API 서버 상태를 확인해 주세요."
    )
    st.stop()

except requests.exceptions.RequestException as e:
    st.error(
        "KOBIS API 요청에 실패했습니다. "
        "인터넷 연결, API 주소, KOBIS 서버 상태를 확인해 주세요."
    )
    st.caption(f"상세 오류: {e}")
    st.stop()

except ValueError:
    st.error(
        "KOBIS API가 올바른 JSON 응답을 보내지 않았습니다. "
        "KOBIS API 서버 상태를 확인해 주세요."
    )
    st.stop()


# ---------------------------------------------------------
# 5. KOBIS가 보내는 오류(faultInfo) 확인
# ---------------------------------------------------------

# KOBIS는 인증키가 틀려도 HTTP 상태 코드가 200일 수 있습니다.
# 따라서 HTTP 상태 코드만 보고 성공했다고 판단하면 안 됩니다.
fault_info = data.get("faultInfo")

if fault_info:
    fault_code = fault_info.get("errorCode", "알 수 없음")
    fault_message = fault_info.get("message", "알 수 없는 오류")

    st.error("KOBIS API에서 오류를 반환했습니다.")
    st.warning(
        f"오류 코드: {fault_code}\n\n"
        f"오류 내용: {fault_message}"
    )
    st.info(
        "다음 사항을 확인해 주세요:\n"
        "- Streamlit Cloud Secrets의 KOBIS_KEY가 정확한지 확인\n"
        "- KOBIS Open API 인증키가 발급·활성화되어 있는지 확인\n"
        "- 조회 날짜가 올바른지 확인\n"
        "- KOBIS API 서버에 장애가 없는지 확인"
    )
    st.stop()


# ---------------------------------------------------------
# 6. 영화 목록 가져오기
# ---------------------------------------------------------

box_office_result = data.get("boxOfficeResult", {})
movie_list = box_office_result.get("dailyBoxOfficeList", [])

# 영화 목록 자체가 없으면 사용자에게 확인할 내용을 보여줍니다.
if not movie_list:
    st.warning("해당 날짜의 박스오피스 영화 목록이 없습니다.")
    st.info(
        "다음 사항을 확인해 주세요:\n"
        "- KOBIS에서 해당 날짜의 일일 박스오피스가 집계되었는지 확인\n"
        "- KOBIS API 응답에 dailyBoxOfficeList가 포함되어 있는지 확인\n"
        "- API 인증키가 정상인지 확인\n"
        "- KOBIS API 서버 상태를 확인"
    )
    st.stop()


# ---------------------------------------------------------
# 7. 데이터를 표 형태로 변환
# ---------------------------------------------------------

# API에서 숫자도 문자열로 오므로 int로 변환합니다.
rows = []

for movie in movie_list:
    rows.append(
        {
            "순위": int(movie.get("rank", 0)),
            "영화명": movie.get("movieNm", ""),
            "개봉일": movie.get("openDt", ""),
            "관객수": int(movie.get("audiCnt", 0)),
            "누적관객": int(movie.get("audiAcc", 0)),
            "스크린수": int(movie.get("scrnCnt", 0)),
        }
    )

df = pd.DataFrame(rows)

# 순위를 숫자로 정렬합니다.
df = df.sort_values("순위").reset_index(drop=True)


# ---------------------------------------------------------
# 8. 1위 영화 지표 카드
# ---------------------------------------------------------

first_movie = df.iloc[0]

st.subheader("🏆 1위 영화")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="영화",
        value=first_movie["영화명"],
    )

with col2:
    st.metric(
        label="관객수",
        value=f"{first_movie['관객수']:,}명",
    )

with col3:
    st.metric(
        label="누적관객",
        value=f"{first_movie['누적관객']:,}명",
    )


# ---------------------------------------------------------
# 9. 관객수 상위 5편 막대그래프
# ---------------------------------------------------------

st.subheader("📊 관객수 상위 5편")

# 관객수가 많은 순서로 정렬한 뒤 최대 5편만 선택합니다.
top5 = (
    df.sort_values("관객수", ascending=False)
    .head(5)
    .set_index("영화명")
)

# Streamlit의 기본 막대그래프를 사용합니다.
st.bar_chart(
    top5["관객수"],
    x_label="영화",
    y_label="관객수",
)


# ---------------------------------------------------------
# 10. 전체 박스오피스 표
# ---------------------------------------------------------

st.subheader("🎞️ 전체 순위")

# 화면에 보여줄 숫자는 천 단위 구분을 적용합니다.
display_df = df.copy()

display_df["관객수"] = display_df["관객수"].map(lambda x: f"{x:,}")
display_df["누적관객"] = display_df["누적관객"].map(lambda x: f"{x:,}")
display_df["스크린수"] = display_df["스크린수"].map(lambda x: f"{x:,}")

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
)
