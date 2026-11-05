/* Run against files extracted from a reproducibly built Monet XPI. Synthetic values only. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
module.exports = async function(root) {
    let count = 0, step = '', calls = [], notices = [];
    const context = vm.createContext({
        browser: {}, window: {top:{location:{origin:'https://example.invalid',href:'https://example.invalid/login'}}},
        logDebug:()=>{},logError:()=>{},tr:x=>x,trimURL:x=>x,
        matchesWithNodeName:(node,name)=>node?.nodeName===name,
        kpxc:{credentials:[],combinations:[],settings:{},setPasswordFilled:async()=>{},rememberCredentials:()=>{}},
        kpxcSites:{combinationExceptionFound:()=>false},
        kpxcUI:{createNotification:(_level,text)=>notices.push(text)},
        kpxcUserAutocomplete:{closeList:()=>{}},ManualFill:{NONE:0},
        sendMessage:async(action,args)=>{calls.push([action,args]);return action==='monet_get_username_step'?step:action==='monet_native_consent'?true:undefined;}
    });
    for(const name of ['fields','form','fill'])vm.runInContext(fs.readFileSync(path.join(root,'content',name+'.js'),'utf8'),context,{filename:name+'.js'});
    const {fields,form,fill}=vm.runInContext('({fields:kpxcFields,form:kpxcForm,fill:kpxcFill})',context);
    fill.setValueWithChange=async(field,value)=>{field.value=value;};
    const field=(name,autocomplete,value='')=>({nodeName:'INPUT',name,autocomplete,value,type:'password',maxLength:-1});
    const current=field('current','section-account current-password');
    const fresh=field('new','section-account new-password'),confirm=field('confirmation','new-password');
    for(const f of [current,fresh,confirm]){fields.hasAutocomplete(f,'');f.autocomplete='off';}
    assert.equal(fields.hasAutocomplete(fresh,'new-password'),true);count++;
    fresh.value='NewSynthetic';confirm.value='DifferentSynthetic';assert.equal(form.getNewPassword([fresh,confirm]),'');
    confirm.value=fresh.value;assert.equal(form.getNewPassword([current,fresh,confirm]),'NewSynthetic');count++;
    const user={nodeName:'INPUT',name:'username',type:'text',value:'',placeholder:'Email address'};
    assert.equal(await form.getUsernameValue(user),'');count++;
    context.kpxc.credentials=[{uuid:'a',login:'alice',password:'AliceSynthetic'},{uuid:'b',login:'bob',password:'BobSynthetic'}];
    step='bob';assert.equal(await form.getUsernameValue(null),'bob');count++;
    context.kpxc.combinations=[{username:user,password:current},{password:fresh},{password:confirm}];
    assert.equal(await fill.fillFromAutofill(),true);assert.equal(current.value,'BobSynthetic');
    assert.equal(fresh.value,'NewSynthetic');assert.equal(confirm.value,'NewSynthetic');count++;
    step='unknown';current.value='';user.value='';assert.equal(await fill.fillFromAutofill(),false);assert.equal(current.value,'');count++;
    step='alice';user.value='bob';assert.equal(await fill.fillFromAutofill(),true);assert.equal(current.value,'BobSynthetic');count++;
    fresh.value='KeepNewSynthetic';await fill.fillInCredentials({password:fresh},'alice','a');
    assert.equal(fresh.value,'KeepNewSynthetic');count++;
    step='';user.value='';calls=[];
    const formNode={nodeName:'FORM',checkValidity:()=>false,querySelector:()=>null};
    form.savedForms=[{form:formNode,username:user,password:current,passwordInputs:[current,fresh,confirm]}];
    await form.onSubmit.call(formNode,{isTrusted:true,type:'submit'});
    assert.equal(form.submitTriggered,false);assert.equal(calls.some(([action])=>action==='page_set_submitted'),false);count++;
    formNode.checkValidity=()=>true;form.savedForms[0].username=null;current.value='SharedSynthetic';
    context.kpxc.credentials.forEach(c=>c.password='SharedSynthetic');calls=[];
    await form.onSubmit.call(formNode,{isTrusted:true,type:'submit'});
    assert.equal(notices.at(-1),'monetChooseAccount');assert.equal(calls.some(([action])=>action==='page_set_submitted'),false);count++;
    context.kpxc.credentials[1].password='BobSynthetic';current.value='BobSynthetic';fresh.value=confirm.value='NewBobSynthetic';
    fields.isVisible=()=>true;calls=[];
    await form.onSubmit.call(formNode,{isTrusted:true,type:'submit'});
    const submitted=calls.find(([action])=>action==='page_set_submitted');
    assert.equal(submitted[1][1],'bob');assert.equal(submitted[1][2],'NewBobSynthetic');count++;
    return count;
};
if(require.main===module)module.exports(process.argv[2]).then(count=>console.log(`${count} password form checks passed`));
