// Runs on the real Electron main process with synthetic credentials only.
const {app, BrowserWindow} = require('electron');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const sdk = require(process.env.MONET_ELECTRON_CLIENT);
const {createClient} = require(path.join(process.env.MONET_ELECTRON_CLIENT, 'bus.cjs'));
const dbus = require(process.env.MONET_TEST_ELECTRON_DBUS);
const mode = process.argv.find(x => x.startsWith('--fixture='))?.split('=')[1] || 'fill';
// The integration must work without the accessibility tree, including Flatpak.
app.commandLine.appendSwitch('disable-renderer-accessibility');
let finished=false;
app.whenReady().then(async () => {
  try {
    const window = new BrowserWindow({width:640,height:480, webPreferences:{sandbox:true, contextIsolation:true,nodeIntegration:false}});
    window.setMenu(null);
    const file=path.join(__dirname,'form.html'), url=pathToFileURL(file).href;
    const bridge=sdk.createIntegration({allowedDocuments:[url],client:createClient(dbus)});
    await window.loadFile(file);window.show();window.focus();
    const service='server.example.invalid/'+mode;
    await window.webContents.executeJavaScript('server.value='+JSON.stringify(service));
    // The native Qt test fixture explicitly clicks Save / Fill in a dummy vault.
    const saved=await bridge.offer(window.webContents,{username:'fixture@example.invalid',password:'synthetic-app-only',service,kind:'login'});
    if(saved.status!=='saved')throw Error('save '+saved.status);
    if(mode==='readonly')await window.webContents.executeJavaScript("user.value='fixture@example.invalid';user.readOnly=true");
    if(mode==='typed')await window.webContents.executeJavaScript("password.value='typed-by-user'");
    const mutations={
      'changed-page':"history.pushState({},'', '?changed')",
      'changed-action':"submit.textContent='Register'",
      'changed-field':"password.outerHTML='<input id=\"password\" type=\"password\" autocomplete=\"current-password\">'",
      'changed-name':"password.name='new_password'",
      'changed-type':"user.type='tel'",
      'typed-during':"password.value='typed-by-user'",
      'changed-user':"user.value='another@example.invalid'",
      'changed-service':"server.value='other.example.invalid'"
    };
    let timer;
    if(mutations[mode])timer=setTimeout(()=>window.webContents.executeJavaScript(mutations[mode]),300);
    const result=await bridge.fill(window.webContents,{username:'#user',password:'#password',service:'#server'});
    clearTimeout(timer);
    const state=await window.webContents.executeJavaScript('({username:user.value,password:password.value,submitted})');
    const expected=['fill','readonly'].includes(mode);
    if(expected ? result.status!=='filled'||state.username!=='fixture@example.invalid'||state.password!=='synthetic-app-only'||state.submitted :
      result.status==='filled'||state.password==='synthetic-app-only'||state.submitted)throw Error('Unexpected fill result '+mode+' '+result.status);
    // No returned password, account, URL token or form content in app result.
    if(Object.keys(result).join()!=='status')throw Error('Credential escaped helper');
    finished=true;app.exit(0);
  }catch(error){console.error(error.message);app.exit(2);}
});
setTimeout(()=>{if(!finished)app.exit(3);},20000);
