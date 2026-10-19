// Existing feature regressions enter the same sections through the new two-level
// navigation. Landing-page defaults and disclosure behavior have dedicated tests.
const assert = require('assert');
const areas = {
 setup:'manage', server:'manage', build:'manage', files:'manage',
 gameplay:'customize', spire:'customize', bots:'customize', appearance:'customize', database:'customize',
 client:'settings', fixes:'settings', logs:'settings', play:'play'
};
async function openDetails(page, selector) {
 const details=page.locator(selector);
 if(await details.count() && await details.isVisible() && await details.getAttribute('open')===null)
  await details.locator(':scope > summary').click();
}
async function openTab(page, name) {
 assert(areas[name], 'Known launcher section: '+name);
 await page.locator('.primary-nav [data-area="'+areas[name]+'"]').click();
 if(name!=='play')await page.locator('.secondary-nav [data-tab="'+name+'"]').click();
 if(name==='setup')await openDetails(page,'#setup-tools');
 if(name==='build')await openDetails(page,'#build-tools');
}
async function openClientOptions(page) {
 await openDetails(page,'#client-options');
 await openDetails(page,'#preferences-recommended');
 await openDetails(page,'#preferences-experiments');
}
async function revealControl(page, id) {
 await page.evaluate(id=>window.navigateToControl(id),id);
}
module.exports={openTab,openDetails,openClientOptions,revealControl};
