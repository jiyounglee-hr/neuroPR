import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import requests
import json
import os
from dotenv import load_dotenv
import openai
import io
import time
import threading

# 환경 변수 로드
load_dotenv()

# 앱 깨우기 함수
def keep_alive():
    while True:
        try:
            # 현재 시간을 sidebar에 업데이트 (보이지 않게)
            placeholder = st.sidebar.empty()
            placeholder.markdown(f"<div style='display: none;'>{datetime.now()}</div>", unsafe_allow_html=True)
            time.sleep(60)  # 1분마다 실행
        except:
            continue

# 백그라운드에서 keep_alive 함수 실행
if 'keep_alive_thread' not in st.session_state:
    keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
    keep_alive_thread.start()
    st.session_state.keep_alive_thread = keep_alive_thread

# 네이버 API 키 설정
NAVER_CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]
NAVER_CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]

# OpenAI API 키 설정
openai.api_key = st.secrets["OPENAI_API_KEY"]

# 페이지 설정
st.set_page_config(
    page_title="뉴로핏 뉴스 대시보드",
    page_icon="📰",
    layout="wide"
)

# 세션 상태 초기화
if 'news_data' not in st.session_state:
    st.session_state.news_data = []

def get_date_range(period):
    today = datetime.now()
    if period == "1주일":
        start_date = today - timedelta(days=7)
    elif period == "2주일":
        start_date = today - timedelta(days=14)
    elif period == "1개월":
        start_date = today - timedelta(days=30)
    elif period == "3개월":
        start_date = today - timedelta(days=90)
    elif period == "6개월":
        start_date = today - timedelta(days=180)
    elif period == "1년":
        start_date = today - timedelta(days=365)
    else:
        return None, None
    
    return start_date.strftime("%Y.%m.%d"), today.strftime("%Y.%m.%d")

def crawl_news(keyword, start_date, end_date):
    news_list = []
    page = 1
    max_pages = 10  # 최대 페이지 수를 10으로 제한 (1000개 결과)
    
    # 사이트명 한글 매핑 딕셔너리
    site_mapping = {
        "zdnet.co.kr": "지디넷코리아",
        "newsis.com": "뉴시스",
        "mt.co.kr": "머니투데이",
        "mk.co.kr": "매일경제",
        "hankyung.com": "한국경제",
        "etnews.com": "전자신문",
        "edaily.co.kr": "이데일리",
        "dt.co.kr": "디지털타임스",
        "dailymedi.com": "데일리메디",
        "chosun.com": "조선일보",
        "biz.chosun.com": "조선비즈",
        "yna.co.kr": "연합뉴스",
        "news1.kr": "뉴스1",
        "sedaily.com": "서울경제",
        "fnnews.com": "파이낸셜뉴스",
        "businesspost.co.kr": "비즈니스포스트",
        "medigatenews.com": "메디게이트뉴스",
        "doctorsnews.co.kr": "메디칼타임즈",
        "moneys.mt.co.kr": "머니S",
        "thebell.co.kr": "더벨",
        "news.mt.co.kr": "머니투데이",
        "news.heraldcorp.com": "헤럴드경제",
        "news.joins.com": "중앙일보"
    }
    
    try:
        while page <= max_pages:
            # 네이버 검색 API 호출
            url = "https://openapi.naver.com/v1/search/news.json"
            headers = {
                "X-Naver-Client-Id": NAVER_CLIENT_ID,
                "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
            }
            params = {
                "query": keyword,
                "display": 100,  # 한 번에 표시할 검색 결과 개수
                "start": (page - 1) * 100 + 1,  # 검색 시작 위치
                "sort": "date"  # 날짜순 정렬
            }
            
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()  # HTTP 오류 체크
            
            data = response.json()
            
            if not data.get("items"):
                break
                
            for item in data["items"]:
                try:
                    # 날짜 파싱
                    pub_date = datetime.strptime(item["pubDate"], "%a, %d %b %Y %H:%M:%S +0900")
                    
                    # 날짜 범위 체크
                    if start_date and end_date:
                        start = datetime.strptime(start_date, "%Y.%m.%d")
                        end = datetime.strptime(end_date, "%Y.%m.%d") + timedelta(days=1)  # 종료일의 다음날 00:00까지 포함
                        if not (start <= pub_date < end):  # 종료일 다음날 00:00 미만까지 포함
                            continue
                    
                    # URL을 매체명으로 사용하고 www.와 .com 등 제거
                    try:
                        url_parts = item["link"].split("/")
                        if len(url_parts) > 2:
                            domain = url_parts[2]
                            # www. 제거
                            if domain.startswith("www."):
                                domain = domain[4:]
                            # .com, .co.kr 등 제거
                            domain = domain.split(".c")[0]
                            press = domain
                        else:
                            press = item["link"]
                    except:
                        press = "알 수 없음"
                    
                    news_list.append({
                        "제목": item["title"].replace("<b>", "").replace("</b>", "").replace("...", "").strip(),
                        "매체": press,
                        "날짜": pub_date,
                        "URL": item["link"]
                    })
                except Exception as e:
                    st.warning(f"기사 처리 중 오류 발생: {str(e)}")
                    continue
            
            # 다음 페이지 확인
            if len(data["items"]) < 100:  # 마지막 페이지
                break
                
            page += 1
            
        if news_list:
            st.success(f"총 {len(news_list)}개의 기사를 수집했습니다.")
        else:
            st.warning("검색 결과가 없습니다.")
            
    except Exception as e:
        st.error(f"뉴스 검색 중 오류 발생: {str(e)}")
    
    return news_list

def generate_news_article(title, content, reference_articles, reference_contents):
    # 프롬프트 구성
    prompt = f"""다음 정보를 바탕으로 보도자료 형식의 뉴스 기사를 작성해주세요.

제목: {title}

주요 내용: {content}

참고할 기사들:
"""

    # 참고 기사 정보 추가
    for i, (article, content) in enumerate(zip(reference_articles, reference_contents), 1):
        if content:
            prompt += f"\n[참고기사 {i}]\n"
            prompt += f"제목: {article['title']}\n"
            prompt += f"매체: {article['press']}\n"
            prompt += f"내용: {content[:500]}...\n"  # 내용은 500자까지만 포함

    prompt += """
작성 지침:
1. 보도자료는 [보도자료]로 시작하며, 제목은 주어진 제목을 그대로 사용합니다.
2. 첫 문단은 핵심 메시지를 간단명료하게 전달합니다.
3. 본문은 다음 구조로 작성합니다:
   - 주요 내용을 구체적으로 설명
   - 관련 업계 동향이나 시장 상황 언급
   - 참고 기사의 내용을 활용하여 신뢰성 보강
4. 문장은 간결하고 객관적으로 작성하며, 전문 용어가 필요한 경우 적절한 설명을 덧붙입니다.
5. 보도자료 말미에는 '관련 동향' 섹션을 추가하여 참고 기사들의 핵심 내용을 3-4줄로 요약합니다.
6. 전체 보도자료는 보통 4-5개 문단으로 구성하며, 각 문단은 2-3개의 문장으로 작성합니다.
7. 모든 문장은 '~다' 체로 작성합니다. (예: '~합니다' 대신 '~다' 사용)
"""

    try:
        # GPT 모델을 사용하여 기사 생성
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "당신은 IT/의료 분야의 전문 보도자료 작성자입니다. 전문성과 객관성을 바탕으로 신뢰도 높은 보도자료를 작성해주세요. 모든 문장은 '~다' 체로 작성합니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        generated_article = response.choices[0].message.content.strip()
        
        # 생성된 기사가 [보도자료]로 시작하는지 확인하고, 아니면 추가
        if not generated_article.startswith("[보도자료]"):
            generated_article = "[보도자료]\n\n" + generated_article
            
        return generated_article
        
    except Exception as e:
        st.error(f"기사 생성 중 오류가 발생했습니다: {str(e)}")
        return f"""[보도자료]

{title}

{content}

관련 동향
- 기사 생성 중 오류가 발생하여 기본 형식으로 표시됩니다.
"""

# 사이드바 설정
st.sidebar.title("NeuroPR")
st.sidebar.write("---")  # 구분선 추가

# 페이지 선택
page = st.sidebar.radio("페이지 선택", ["📰 뉴스 목록", "📜 뉴스 초안 작성"])

# 뉴스 목록 페이지에서만 검색 설정 표시
if page == "📰 뉴스 목록":
    # 공통 검색 설정
    st.sidebar.subheader("검색 설정")
    keyword = st.sidebar.text_input("검색어", value="뉴로핏")
    period = st.sidebar.selectbox(
        "검색 기간",
        ["1주일", "2주일", "1개월", "3개월", "6개월", "1년", "직접입력"]
    )

    if period == "직접입력":
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date = st.date_input("시작일")
        with col2:
            end_date = st.date_input("종료일")
        start_date = start_date.strftime("%Y.%m.%d")
        end_date = end_date.strftime("%Y.%m.%d")
    else:
        start_date, end_date = get_date_range(period)

    # 최초 로딩 시 1주일치 뉴스 자동 검색
    if 'first_load' not in st.session_state:
        st.session_state.first_load = True
        with st.spinner("뉴스를 검색하고 있습니다..."):
            news_data = crawl_news(keyword, start_date, end_date)
            st.session_state.news_data = news_data

    if st.sidebar.button("뉴스 검색"):
        with st.spinner("뉴스를 검색하고 있습니다..."):
            news_data = crawl_news(keyword, start_date, end_date)
            st.session_state.news_data = news_data

# 페이지별 콘텐츠
if page == "📰 뉴스 목록":
    # 메인 대시보드
    if st.session_state.news_data:
        # 데이터프레임 생성
        df = pd.DataFrame(st.session_state.news_data)
        df.insert(0, "No", range(1, len(df) + 1))
        
        # 뉴스 목록
        col1, col2 = st.columns([6, 1])  # 6:1 비율로 컬럼 분할
        with col1:
            st.subheader("📰 뉴스 목록")
        with col2:
            # Excel 다운로드 버튼
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                download_df = df[['No', '제목', '매체', '날짜', 'URL']]
                download_df['날짜'] = download_df['날짜'].dt.strftime('%Y-%m-%d %H:%M')
                download_df.to_excel(writer, sheet_name='뉴스목록', index=False)
                
                # 열 너비 자동 조정
                worksheet = writer.sheets['뉴스목록']
                for idx, col in enumerate(download_df.columns):
                    series = download_df[col]
                    max_len = max(
                        series.astype(str).map(len).max(),
                        len(str(series.name))
                    ) + 2
                    worksheet.set_column(idx, idx, max_len)
            
            excel_data = output.getvalue()
            
            st.download_button(
                label="📥 Excel 다운로드",
                data=excel_data,
                file_name=f"뉴스목록_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        # URL을 클릭 가능한 링크로 변환
        def make_clickable(url):
            return f'<a href="{url}" target="_blank">원문</a>'
        
        # 표시할 데이터프레임 준비
        display_df = df.copy()
        display_df['원문 링크'] = display_df['URL'].apply(make_clickable)
        display_df = display_df[['No', '제목', '매체', '날짜', '원문 링크']]
        
        # 날짜 형식 변환
        display_df['날짜'] = display_df['날짜'].dt.strftime('%Y-%m-%d %H:%M')
        
        # CSS 스타일 추가
        st.markdown("""
            <style>
            table {
                width: 100%;
                border-collapse: collapse;
            }
            th {
                background-color: #f0f2f6;
                font-weight: bold;
                padding: 8px;
                border: 1px solid #ddd;
                text-align: center;
            }
            td {
                padding: 8px;
                border: 1px solid #ddd;
            }
            tr:nth-child(even) {
                background-color: #f9f9f9;
            }
            tr:hover {
                background-color: #f5f5f5;
            }
            </style>
        """, unsafe_allow_html=True)
        
        # 데이터프레임 HTML로 변환 및 표시
        st.write(display_df.to_html(escape=False, index=False), unsafe_allow_html=True)
        
        # 공백 추가
        st.write("")
    else:
        st.info("왼쪽 사이드바에서 검색어와 기간을 설정한 후 '뉴스 검색' 버튼을 클릭하세요.")

else:  # 📜 뉴스 초안 작성 페이지
    st.subheader("📜 뉴스 초안 작성")
    
    # 입력 필드 스타일 추가
    st.markdown("""
        <style>
        .stTextInput>div>div>input {
            font-size: 16px;
        }
        .stTextArea>div>div>textarea {
            font-size: 16px;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # 입력 폼
    with st.form("news_draft_form"):
        title = st.text_input("제목", placeholder="뉴스 제목을 입력하세요")
        
        st.write("")  # 간격 추가
        
        content = st.text_area("주요내용", 
            value="\n\n\n\n\n\n\n\n\n\n\n\n2016년에 설립된 뉴로핏(공동대표이사 빈준길, 김동현)은 인공지능(AI) 기술 기반으로 '진단, 치료 가이드, 치료' 전주기에 걸친 뇌 영상 분석 솔루션 및 치료 의료기기를 연구 개발하는 전문기업이다. 광주과학기술원(GIST)에서 차세대 뉴로네비게이션 시스템을 개발한 빈준길, 김동현 뉴로핏 공동 대표가 함께 창업했다.\n\n뉴로핏은 뇌의 난제를 해결한다는 미션 아래 뇌질환 진단과 치료를 선도하는 글로벌 리딩 컴퍼니가 되기 위한 행보를 이어나가고 있다. 뇌 과학 분야의 전문성을 바탕으로 미지의 영역인 인간의 뇌를 탐구하고 뇌질환 의료 AI 솔루션 분야의 선구자가 되기 위해 끊임없이 도전하고 성장하고 있다.",
            placeholder="뉴스에 포함될 주요 내용을 입력하세요", 
            height=400)
        
        st.write("")  # 간격 추가
        
        # 초안 작성 버튼
        submitted = st.form_submit_button("📝 초안 작성", use_container_width=True)
    
    if submitted:
        if not title or not content:
            st.error("제목과 주요내용을 모두 입력해주세요.")
        else:
            with st.spinner("뉴스 초안을 작성하고 있습니다..."):
                # 새로운 기사 생성
                generated_article = generate_news_article(title, content, [], [])
                
                # 결과 표시
                st.success("뉴스 초안이 작성되었습니다!")
                
                # 탭으로 결과 구분
                tab1, tab2 = st.tabs(["📝 작성된 초안", "✍️ 편집"])
                
                with tab1:
                    st.markdown("### 📰 뉴스 초안")
                    st.markdown("---")
                    
                    # 메타 정보
                    st.markdown(f"**작성일자**: {datetime.now().strftime('%Y-%m-%d')}")
                    
                    st.markdown("---")
                    
                    # 생성된 기사 표시
                    paragraphs = generated_article.split('\n')
                    for p in paragraphs:
                        if p.strip():
                            st.markdown(p)
                            st.markdown("")
                
                with tab2:
                    st.markdown("### ✍️ 편집하기")
                    
                    # 편집용 폼
                    with st.form("edit_form"):
                        edited_article = st.text_area("기사 편집", value=generated_article, height=600)
                        edit_submitted = st.form_submit_button("✍️ 수정사항 적용", use_container_width=True)
                    
                    if edit_submitted:
                        st.session_state.edited_article = edited_article
                        st.success("수정사항이 적용되었습니다!")
                        st.rerun()
    else:
        st.info(" ") 