// Usage: node tests/smoke/run.mjs <base-url> [query] [screenshot.png]
// Prints window.SMOKE as JSON, plus rss_bytes (memory of the browser's processes when done);
// exit 1 on an engine error or a failed file. The browser locale is en-US: the page sets the engine locale.
import {execSync} from 'node:child_process';
import {chromium} from 'playwright';

// Resident memory of a process and all its descendants
function treeRss(pid) {
	const rows = execSync('ps -eo pid=,ppid=,rss=').toString().trim().split('\n').map((l) => l.trim().split(/\s+/).map(Number));
	const pids = new Set([pid]);
	let grew = true;
	while (grew) {
		grew = false;
		for (const [p, pp] of rows) {
			if (pids.has(pp) && !pids.has(p)) {
				pids.add(p);
				grew = true;
			}
		}
	}
	return rows.filter(([p]) => pids.has(p)).reduce((sum, [, , rss]) => sum + rss * 1024, 0);
}

const [base, query = '', shot] = process.argv.slice(2);
const browser = await chromium.launch();
const page = await browser.newPage({viewport: {width: 1280, height: 800}, locale: 'en-US'});
let errors = 0;
page.on('console', (m) => { if (m.type() === 'error' && errors++ < 20) console.error('[console]', m.text()); });
page.on('pageerror', (e) => console.error('[pageerror]', e.message));
await page.goto(base.replace(/\/$/, '') + '/?' + query);
await page.waitForFunction(() => window.SMOKE && window.SMOKE.done, null, {timeout: 900000});
if (shot) {
	await page.waitForTimeout(5000);
	await page.screenshot({path: shot});
}
const r = await page.evaluate(() => window.SMOKE);
// Chromium is a child of this process: its memory is the tree minus node itself
r.rss_bytes = treeRss(process.pid) - process.memoryUsage().rss;
console.log(JSON.stringify(r, null, 2));
await browser.close();
process.exit(r.error || r.results.length === 0 || r.results.some((x) => !x.ok) ? 1 : 0);
