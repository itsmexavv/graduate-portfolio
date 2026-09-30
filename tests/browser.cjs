/* Optional browser workflow verification against a fresh, disposable data set. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const base = process.env.PORTFOLIO_URL || 'http://127.0.0.1:8765';
const screenshots = path.resolve(__dirname, '../docs/screenshots');
fs.mkdirSync(screenshots, {recursive:true});

(async () => {
  const browser = await chromium.launch({headless:true});
  const page = await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];
  page.on('pageerror', error=>errors.push(error.message));
  page.on('console', message=>{if(message.type()==='error' && !message.text().includes('422 (Unprocessable Entity)')) errors.push(message.text());});
  async function open(app) { await page.goto(base+(app?`/?app=${app}`:'')); await page.waitForLoadState('networkidle'); }
  async function shot(name) { await page.screenshot({path:path.join(screenshots,`${name}.png`),fullPage:true}); }
  try {
    await open();
    assert.equal(await page.locator('.card').count(),6);
    await shot('overview');
    await open('smartfind');
    assert.equal(await page.locator('#products tr').count(),4);
    await shot('smartfind');
    await page.locator('#search').fill('notebook');
    assert.equal(await page.locator('#products tr').count(),1);
    await page.locator('#search').fill('');
    const form=page.locator('#add-product');
    await form.locator('[name="name"]').fill('Browser demo pencil');
    await form.locator('[name="sku"]').fill('BROWSER-001');
    await form.locator('[name="category"]').fill('Writing');
    await form.locator('[name="price"]').fill('12.25');
    await form.locator('[name="stock"]').fill('3');
    await form.locator('button').click();
    await page.getByText('Browser demo pencil',{exact:true}).first().waitFor();
    const adjust=page.locator('#adjust-stock');
    await adjust.locator('select').selectOption({label:'Browser demo pencil'});
    await adjust.locator('[name="delta"]').fill('2');
    await adjust.locator('[name="reason"]').fill('Browser verification');
    await adjust.locator('button').click();
    await page.getByText('Browser verification',{exact:false}).waitFor();
    await open('attendance');
    await shot('attendance');
    await page.locator('#records button').first().click();
    await page.getByRole('button',{name:'Check out',exact:true}).waitFor();
    await page.getByRole('button',{name:'Check out',exact:true}).click();
    await page.getByText('Completed',{exact:true}).last().waitFor();
    const student=page.locator('#student-form');
    await student.locator('[name="student_no"]').fill('BROWSER-001');
    await student.locator('[name="name"]').fill('Browser Demo Student');
    await student.locator('button').click();
    await page.getByText('Browser Demo Student',{exact:true}).waitFor();
    const event=page.locator('#event-form');
    await event.locator('[name="name"]').fill('Browser Demo Event');
    await event.locator('button').click();
    await page.waitForFunction(()=>document.querySelector('#event-select').selectedOptions[0].textContent.includes('Browser Demo Event'));
    await page.waitForFunction(()=>{const tags=[...document.querySelectorAll('#records .tag')]; return tags.length===4 && tags.every(tag=>tag.textContent==='Absent');});
    await open('peso');
    await shot('peso');
    const transaction=page.locator('#transaction-form');
    await transaction.locator('[name="category"]').fill('Browser test');
    await transaction.locator('[name="amount"]').fill('12.25');
    await transaction.locator('button').click();
    await page.locator('#transactions').getByText('Browser test',{exact:true}).waitFor();
    await open('accesspath');
    await page.locator('#route-form button').click();
    await page.getByText('220 metres',{exact:true}).waitFor();
    assert.equal(await page.locator('#map line.route').count(),3);
    await shot('accesspath');
    await page.locator('[name="step_free"]').uncheck();
    await page.locator('#route-form button').click();
    await page.getByText('170 metres',{exact:true}).waitFor();
    await page.locator('[name="step_free"]').check();
    await page.locator('#segments button[data-id="6"]').click();
    await page.getByText('Path conditions changed.',{exact:false}).waitFor();
    await page.locator('#route-form button').click();
    await page.getByText('No route available',{exact:true}).waitFor();
    await open('minilang');
    await page.locator('#code-form button').click();
    await page.waitForFunction(()=>document.querySelector('#result').textContent==='3\n6\n9\n12\n70');
    await shot('minilang');
    await page.getByRole('button',{name:'AST',exact:true}).click();
    assert.ok((await page.locator('#result').textContent()).includes('Program'));
    await page.locator('#source').fill('print 1/0;');
    await page.locator('#code-form button').click();
    await page.waitForFunction(()=>document.querySelector('#result').textContent.includes('Division by zero'));
    await page.setViewportSize({width:390,height:844});
    for (const app of ['', 'smartfind','attendance','peso','accesspath','minilang']) {
      await open(app);
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`Page overflows on mobile: ${app||'overview'}`);
    }
    await open();
    await shot('mobile-overview');
    assert.deepEqual(errors,[]);
    console.log('PASS: all five browser workflows, desktop screenshots and six mobile layouts; no browser errors.');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
