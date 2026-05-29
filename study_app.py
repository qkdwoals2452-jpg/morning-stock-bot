import streamlit as st
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.set_page_config(page_title="신문기사 공부장", page_icon="📰")

st.title("📰 신문기사 공부장")
st.write("네이버 기사 URL 또는 기사 내용을 넣으면 쉽게 정리해줍니다.")

url = st.text_input("네이버 기사 URL")
title = st.text_input("기사 제목")
article = st.text_area("기사 내용 붙여넣기", height=300)


def get_naver_article(url):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")

    title_tag = soup.select_one("#title_area span")
    content_tag = soup.select_one("#dic_area")

    article_title = title_tag.get_text(strip=True) if title_tag else ""
    article_content = content_tag.get_text("\n", strip=True) if content_tag else ""

    return article_title, article_content


if st.button("분석하기"):

    final_title = title
    final_article = article

    if url:
        try:
            final_title, final_article = get_naver_article(url)
        except Exception as e:
            st.error("기사 URL을 읽지 못했습니다. 기사 내용을 직접 붙여넣어 주세요.")
            st.stop()

    if final_article == "":
        st.warning("기사 URL 또는 기사 내용을 입력해주세요.")
    else:
        prompt = f"""
너는 경제신문을 쉽게 설명해주는 한국 주식 전문가다.

아래 기사 내용을 분석해서 다음 형식으로 정리해줘.

[기사 제목]
{final_title}

[기사 내용]
{final_article}

정리 형식:

1. 기사 내용 정리
- 기사 전체 흐름 설명
- 핵심 내용 자세히 정리
- 신문기사 읽듯 자연스럽게 설명

2. 핵심 포인트 3가지

3. 초보자용 쉬운 설명

4. 어려운 용어 설명
- 용어:
- 뜻:

5. 왜 중요한 기사인가?

6. 한국 증시에 미칠 영향

7. 관련 테마

8. 관련 종목
- 대장주
- 후발주
- 이유

9. 투자자가 주의할 점

10. 내가 외워야 할 한 문장
"""

        with st.spinner("분석 중입니다..."):
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

        result = response.choices[0].message.content
        st.markdown(result)
