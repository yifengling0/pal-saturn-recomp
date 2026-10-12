const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {stripTypeScriptTypes} = require('node:module');
const code = stripTypeScriptTypes(fs.readFileSync(process.argv[2],'utf8').replace(/^import .*;\n/gm,''),{mode:'transform'}).replace('export class','class');
const tick = ()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  let calls=0, bindings=0, detached=0, listener, acquisition=0, fail=false, invalid=false, reports=[];
  const main={
    getWindowProperties:()=>({type:invalid?16:32}),
    on:(event,cb)=>{assert.equal(event,'windowEvent'); bindings++; listener=cb;},
    off:(event,cb)=>{assert.equal(cb,listener);detached++;},
    setPreferredOrientation:async value=>{assert.equal(value,7);calls++; if(fail)throw new Error('denied');}
  };
  const deviceInfo={deviceType:'phone',sdkApiVersion:26};
  let pending;
  const window={WindowType:{TYPE_MAIN:32},Orientation:{AUTO_ROTATION_LANDSCAPE:7},WindowEventType:{WINDOW_SHOWN:1,WINDOW_ACTIVE:2,WINDOW_DESTROYED:7},getLastWindow:async()=>{acquisition++;if(pending)return pending; return main;}};
  const scope={window,deviceInfo};vm.createContext(scope);vm.runInContext(code+'\nthis.Policy=PhoneOrientation;',scope);
  const policy=new scope.Policy({},m=>reports.push(m));
  policy.refresh();policy.refresh();await tick();assert.equal(acquisition,1);assert.equal(bindings,1);assert.equal(calls,1);
  listener(1);listener(2);await tick();assert.equal(calls,3);
  fail=true;listener(2);await tick();assert(reports.at(-1).includes('系统未允许'));fail=false;
  listener(7);assert.equal(detached,1);policy.refresh();await tick();assert.equal(acquisition,2);
  policy.stop();assert.equal(detached,2);const before=calls;policy.refresh();listener(1);await tick();assert.equal(calls,before);
  deviceInfo.deviceType='tablet';const tablet=new scope.Policy({},()=>assert.fail('tablet report'));tablet.refresh();await tick();assert.equal(acquisition,2);tablet.stop();
  deviceInfo.deviceType='2in1';const pc=new scope.Policy({},()=>assert.fail('pc report'));pc.refresh();await tick();assert.equal(acquisition,2);pc.stop();
  deviceInfo.deviceType='phone';invalid=true;const retry=new scope.Policy({},m=>reports.push(m));retry.refresh();await tick();assert.equal(acquisition,3);assert.equal(bindings,2);invalid=false;retry.refresh();await tick();assert.equal(acquisition,4);assert.equal(bindings,3);retry.stop();
  let resolve;pending=new Promise(r=>resolve=r);const late=new scope.Policy({},()=>assert.fail('late report'));late.refresh();late.stop();resolve(main);await tick();assert.equal(bindings,3);
  console.log('8 orientation scenarios passed (phone, resume, failure, reacquisition, stop, tablet, PC, late result)');
})().catch(e=>{console.error(e);process.exitCode=1;});
