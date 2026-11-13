// Launches headless Chromium for the browser tests. In minimal containers the bundled Chromium needs its
// shared libraries extracted first; see docs/TEST_REPORT.md ("Browser tests").
import chromium from '@sparticuz/chromium';
import puppeteer from 'puppeteer-core';

export async function launch(extraArgs = []) {
  return puppeteer.launch({
    args: [...chromium.args, '--use-fake-ui-for-media-stream', ...extraArgs],
    executablePath: process.env.CHROME_PATH || await chromium.executablePath(),
    headless: 'shell',
  });
}
