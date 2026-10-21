// 네이버 뉴스 검색에서 기사 목록을 긁는다.
//
// 네이버 뉴스에 등록된 모든 언론사(news.naver.com/main/officeList.naver)가 검색 대상이라,
// 일반 웹 검색이 놓치는 전문지·업계지까지 잡힌다. 실제로 더벨·비즈월드·딜라이트닷넷·
// 뉴스브라이트 같은 매체는 일반 검색으로는 거의 안 나온다.
//
// 쓰는 법 — Playwright의 browser_run_code_unsafe에 이 파일 경로를 넘긴다.
//
// 지난 날짜를 메울 때는 TARGET_DATE를 박은 사본을 만들어 그 사본을 실행한다.
// 이 파일은 통째로 실행되는 함수라 인자를 받을 수 없고, 추적 중인 원본을
// 실행 때마다 고치면 당일 수집이 망가지기 때문이다. 절차는 daily_update.md의
// '지난 날짜 메우기'에 있다.
// 네이버는 클래스명을 난독화하므로 'fds-news-item-list'와 'headline'처럼
// 그나마 의미가 남아 있는 조각만 붙잡는다. 결과가 0건이면 셀렉터가 바뀐 것이니
// 페이지 구조를 다시 확인해야 한다.

async (page) => {
  // null이면 당일 수집. 'YYYY-MM-DD'를 넣으면 그 하루만 소급 수집한다.
  const TARGET_DATE = null;

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

  // 당일 모드에서만 쓴다. 'N분 전'과 'N시간 전'만 오늘일 수 있고,
  // 시간이 지금 시각을 넘어서면 어제 것이다.
  const isToday = (when) => {
    if (!when) return false;
    if (when.endsWith('분 전')) return true;
    const hours = when.match(/^(\d+)시간 전$/);
    if (!hours) return false;
    return Number(hours[1]) <= new Date().getHours();
  };

  // 날짜 모드에서는 범위를 URL로 이미 못박았으므로 상대시간을 다시 따지지 않는다.
  // '5일 전' 같은 값으로는 게재일을 정확히 가릴 수 없고, 가리려 들면 멀쩡한 기사를
  // 떨어뜨린다. 대신 when을 그대로 실어 보내 교차 확인에 쓴다.
  const inRange = (when) => (TARGET_DATE ? true : isToday(when));

  const searchUrl = (query) => {
    const base =
      'https://search.naver.com/search.naver?where=news&sort=1&query=' +
      encodeURIComponent(query);
    if (!TARGET_DATE) return base + '&pd=4';
    const dots = TARGET_DATE.replace(/-/g, '.');
    const digits = TARGET_DATE.replace(/-/g, '');
    return (
      base +
      '&pd=3&ds=' + dots + '&de=' + dots +
      '&nso=' + encodeURIComponent('so:r,p:from' + digits + 'to' + digits + ',a:all')
    );
  };

  const scrape = async (query) => {
    await page.goto(searchUrl(query), { waitUntil: 'domcontentloaded', timeout: 45000 });
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
  const hits = [];
  const outside = [];

  for (const query of QUERIES) {
    let rows = [];
    try {
      rows = await scrape(query);
    } catch (error) {
      hits.push({ query, error: String(error).slice(0, 120) });
      continue;
    }
    for (const row of rows) {
      if (seen.has(row.url)) continue;
      seen.add(row.url);
      (inRange(row.when) ? hits : outside).push({ ...row, query });
    }
  }

  return {
    기준일: TARGET_DATE || '오늘',
    검색어수: QUERIES.length,
    대상일: hits.length,
    대상일기사: hits,
    참고_범위밖: outside.slice(0, 25),
  };
}
