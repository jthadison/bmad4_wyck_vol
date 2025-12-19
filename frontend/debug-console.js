import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  // Capture console messages
  page.on('console', msg => console.log('BROWSER CONSOLE:', msg.type(), msg.text()));

  // Capture page errors
  page.on('pageerror', error => console.log('PAGE ERROR:', error.message));

  try {
    await page.goto('http://localhost:4173/', { waitUntil: 'networkidle', timeout: 10000 });

    // Wait a bit for Vue to mount
    await page.waitForTimeout(2000);

    // Check if #app is visible
    const appVisible = await page.isVisible('#app');
    console.log('App element visible:', appVisible);

    // Get the HTML of #app
    const appHTML = await page.innerHTML('#app');
    console.log('App HTML length:', appHTML.length);
    console.log('App HTML:', appHTML.substring(0, 200));

  } catch (error) {
    console.log('Error:', error.message);
  }

  await browser.close();
})();
