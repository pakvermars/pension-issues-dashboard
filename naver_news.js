// 네이버 뉴스 검색에서 기사 목록을 긁는다.
//
// 네이버 뉴스에 등록된 모든 언론사(news.naver.com/main/officeList.naver)가 검색 대상이라,
// 일반 웹 검색이 놓치는 전문지·업계지까지 잡힌다. 실제로 더벨·비즈월드·딜라이트닷넷·
// 뉴스브라이트 같은 매체는 일반 검색으로는 거의 안 나온다.
//
// 쓰는 법 — Playwright의 browser_run_code_unsafe에 이 파일 내용을 넣고 QUERIES를 바꾼다.
// 네이버는 클래스명을 난독화하므로 'fds-news-item-list'와 'headline'처럼
// 그나마 의미가 남아 있는 조각만 붙잡는다. 결과가 0건이면 셀렉터가 바뀐 것이니
// 페이지 구조를 다시 확인해야 한다.

async (page) => {
  const QUERIES = [
    '퇴직연금',
    '기금형 퇴직연금',
    '퇴직연금 의무화 사외적립',
    'IRP 개인형퇴직연금',
    '퇴직연금 디폴트옵션',
    '퇴직연금 수익률',
    '퇴직연금 적립금',
    'DB형 적립금 운용',
    '퇴직연금 OCIO 위탁운용',
    '퇴직연금 실물이전',
    '퇴직연금 TDF ETF',
    '연금개혁',
  ];

  // 상대시간 문자열을 '오늘 기사인가'로 바꾼다. 'N분 전'과 'N시간 전'만 오늘일 수 있고,
  // 시간이 지금 시각을 넘어서면 어제 것이다.
  const isToday = (when) => {
    if (!when) return false;
    if (when.endsWith('분 전')) return true;
    const hours = when.match(/^(\d+)시간 전$/);
    if (!hours) return false;
    return Number(hours[1]) <= new Date().getHours();
  };

  const scrape = async (query) => {
    const url =
      'https://search.naver.com/search.naver?where=news&sort=1&pd=4&query=' +
      encodeURIComponent(query);
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await page.waitForTimeout(2200);

    return page.evaluate(() => {
      const TIME = /(\d+분 전|\d+시간 전|\d+일 전|\d{4}\.\d{2}\.\d{2}\.)/;
      const rows = [];
      document.querySelectorAll('[class*="fds-news-item-list"]').forEach((list) => {
        Array.from(list.children).forEach((item) => {
          const head = item.querySelector('[class*="headline"]');
          if (!head) return;
          const link = head.closest('a[href]') || head.querySelector('a[href]');
          if (!link) return;
          const source = item.querySelector('[class*="profile-source"]');
          rows.push({
            title: head.innerText.trim(),
            url: link.href.split('?utm_')[0],
            press: source
              ? source.innerText.replace(/새 창 열림|언론사 선정|선정/g, '').trim().split('\n')[0]
              : null,
            when: (item.innerText.match(TIME) || [])[1] || null,
          });
        });
      });
      return rows;
    });
  };

  const seen = new Set();
  const today = [];
  const older = [];

  for (const query of QUERIES) {
    let rows = [];
    try {
      rows = await scrape(query);
    } catch (error) {
      today.push({ query, error: String(error).slice(0, 120) });
      continue;
    }
    for (const row of rows) {
      if (seen.has(row.url)) continue;
      seen.add(row.url);
      (isToday(row.when) ? today : older).push({ ...row, query });
    }
  }

  return {
    검색어수: QUERIES.length,
    오늘: today.length,
    오늘기사: today,
    참고_이전기사: older.slice(0, 25),
  };
}
