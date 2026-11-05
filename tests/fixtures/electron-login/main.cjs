// Private accessibility acceptance app. All accounts and pages are synthetic.
const {app, BrowserWindow} = require('electron');
const path = require('node:path');
const mode = process.argv.find(x => x.startsWith('--fixture='))?.split('=')[1] || 'fill';
app.commandLine.appendSwitch('force-renderer-accessibility', 'complete');
app.whenReady().then(async () => {
  app.setAccessibilitySupportEnabled(true);
  const window = new BrowserWindow({width:640,height:480, webPreferences:{sandbox:true, contextIsolation:true, nodeIntegration:false}});
  window.setMenu(null);
  await window.loadFile(path.join(__dirname, 'form.html'));
  window.show(); window.focus();
  await window.webContents.executeJavaScript(`window.fixtureMode = ${JSON.stringify(mode)}; startFixture();`);
  setTimeout(async () => {
    try {
      const good = await window.webContents.executeJavaScript('verifyFixture()');
      app.exit(good ? 0 : 1);
    } catch { app.exit(2); }
  }, 5000);
});
setTimeout(() => app.exit(3), 12000);
