// 오늘 기사 URL 목록만 긁어 온다. 게이트(gate.py)가 쓴다.
//
// naver_news.js와 달리 이 파일은 Playwright MCP가 아니라 Node에서 단독으로 돈다.
// 자기 브라우저를 띄우고 바로 닫으므로, Claude 세션이 쓰는 MCP 브라우저 프로필과
// 부딪히지 않는다(launch()는 임시 프로필을 쓴다. launchPersistentContext가 아니다).
//
// 검색어는 넓은 것 둘만 쓴다. 새 기사가 있는지만 알면 되고, 실제 수집은
// naver_news.js가 검색어 12개를 다 돈다. 15분마다 12개를 긁으면 네이버 요청이
// 하루 600회를 넘어 차단 위험이 있다.
//
// ⚠ 셀렉터가 깨지면 이 파일과 naver_news.js를 **둘 다** 고쳐야 한다.
//    같은 DOM을 두 군데서 읽고 있다.

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const QUERIES = ['퇴직연금', '연금개혁'];

// playwright-core는 브라우저를 직접 받지 않는다. Playwright MCP가 이미 받아 둔
// ms-playwright 캐시에서 chrome.exe를 찾아 쓴다.
function chromePath() {
  const cache = path.join(process.env.LOCALAPPDATA || '', 'ms-playwright');
  const dir = fs
    .readdirSync(cache)
    .filter((name) => name.startsWith('chromium-'))
    .sort()
    .pop();
  if (!dir) throw new Error(`ms-playwright에 chromium이 없다: ${cache}`);
  return path.join(cache, dir, 'chrome-win64', 'chrome.exe');
}

// 상대시간 문자열을 '오늘 기사인가'로 바꾼다. naver_news.js와 같은 규칙이다.
const isToday = (when) => {
  if (!when) return false;
  if (when.endsWith('분 전')) return true;
  const hours = when.match(/^(\d+)시간 전$/);
  if (!hours) return false;
  return Number(hours[1]) <= new Date().getHours();
};

async function scrape(page, query) {
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
        rows.push({
          url: link.href.split('?utm_')[0],
          when: (item.innerText.match(TIME) || [])[1] || null,
        });
      });
    });
    return rows;
  });
}

(async () => {
  let browser;
  try {
    browser = await chromium.launch({ headless: true, executablePath: chromePath() });
    const page = await browser.newPage({
      userAgent:
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
        '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
    });

    const seen = new Set();
    const 오늘 = [];
    let 이전 = 0;

    for (const query of QUERIES) {
      for (const row of await scrape(page, query)) {
        if (seen.has(row.url)) continue;
        seen.add(row.url);
        if (isToday(row.when)) 오늘.push(row.url);
        else 이전 += 1;
      }
    }

    process.stdout.write(JSON.stringify({ 오늘, 이전 }));
  } catch (error) {
    // 실패는 숨기지 않는다. 오늘·이전 모두 0이면 게이트가 셀렉터 파손으로 보고
    // 수집을 돌려, 문제가 사람 눈에 보이는 자리까지 올라온다.
    process.stdout.write(
      JSON.stringify({ 오늘: [], 이전: 0, 오류: String(error).slice(0, 200) })
    );
  } finally {
    if (browser) await browser.close();
  }
})();
