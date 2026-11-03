/* Synthetic submissions only. Run with Node, or require from the test runtime. */
const assert = require('node:assert/strict');
const crypto = require('node:crypto').webcrypto;
const Gate = require('../browser/monet-passwords/automatic-submit.js');
module.exports = async function () {
    let count = 0, calls = [], now = 1000;
    const tab = {id: 3, url: 'https://example.invalid/login'};
    const data = [true, 'test', 'synthetic-only', tab.url, []];
    let gate = new Gate(async (_, candidate) => {calls.push(candidate);return {prompted:true,saved:false};},crypto,()=>now);
    assert.equal(await gate.submit(tab,data),true);
    assert.equal(await gate.submit(tab,data),false);
    assert.equal(calls.length,1); count++;
    now+=120001;assert.equal(await gate.submit(tab,data),true);count++;
    const changed=[true,'test','new-synthetic-only',tab.url,[{login:'test',uuid:'one'}]];
    assert.equal(await gate.submit(tab,changed),true);assert.equal(calls.at(-1).uuid,'one');count++;
    assert.equal(JSON.stringify([...gate.recent.values()]).includes('synthetic'),false);count++;
    for(const args of [[true,'test','secret','https://other.invalid',[]],[true,'test','secret','http://example.invalid',[]],
                      [true,'test','','https://example.invalid',[]],[false,'test','secret',tab.url,[]]]) {
        const before=calls.length;assert.equal(await gate.submit(tab,args),false);assert.equal(calls.length,before);
    } count++;
    let finish;gate=new Gate(()=>new Promise(resolve=>{finish=resolve;}),crypto);
    const first=gate.submit(tab,data);
    while(!finish)await new Promise(resolve=>setTimeout(resolve,1));
    assert.equal(await gate.submit(tab,data),false);finish({prompted:true,saved:true});await first;count++;
    let attempts=0;gate=new Gate(async()=>{attempts++;return [];},crypto);
    await gate.submit(tab,data);await gate.submit(tab,data);assert.equal(attempts,2);count++;
    attempts=0;gate=new Gate(async()=>{attempts++;throw new Error('fixture disconnect');},crypto);
    await assert.rejects(gate.submit(tab,data));await assert.rejects(gate.submit(tab,data));
    assert.equal(attempts,2);count++;
    gate=new Gate(async()=>({prompted:true,saved:true}),crypto,()=>now);
    for(let id=0;id<128;id++)await gate.submit({...tab,id},data);
    assert.equal(await gate.submit({...tab,id:129},data),false);assert.equal(gate.recent.size,128);count++;
    return count;
};
if(require.main===module)module.exports().then(count=>console.log(`${count} automatic submission checks passed`));
