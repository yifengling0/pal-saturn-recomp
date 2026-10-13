const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {stripTypeScriptTypes} = require('node:module');
const code = stripTypeScriptTypes(fs.readFileSync(process.argv[2],'utf8').replace(/^import .*;\n/gm,''),{mode:'transform'}).replace('export class','class');
const tick = ()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  let calls=0, bindings=0, detached=0, acquisition=0, failAcquire=false, failListen=false, failApply=false;
  let listener, lifecycle, registrations=0, unregistrations=0, pending;
  const reports=[], logs=[], timers=new Map(); let timerId=0;
  const main={
    // Deliberately NOT TYPE_MAIN: stage identity, not a version/type guess, is authoritative.
    getWindowProperties:()=>({type:1,windowRect:{width:1280,height:2832}}),
    on:(event,cb)=>{assert.equal(event,'windowEvent');if(failListen)throw {code:1300002};bindings++;listener=cb;},
    off:(event,cb)=>{assert.equal(cb,listener);detached++;},
    setPreferredOrientation:async value=>{assert.equal(value,7);calls++;if(failApply)throw {code:1300002};}
  };
  const deviceInfo={deviceType:'phone',sdkApiVersion:26};
  const window={Orientation:{AUTO_ROTATION_LANDSCAPE:7},WindowEventType:{WINDOW_SHOWN:1,WINDOW_ACTIVE:2,WINDOW_DESTROYED:7},getLastWindow:()=>assert.fail('must not acquire picker/top window')};
  const app={on:(type,cb)=>{assert.equal(type,'abilityLifecycle');registrations++;lifecycle=cb;return 9;},off:async(type,id)=>{assert.equal(id,9);unregistrations++;}};
  const ability={context:{getApplicationContext:()=>app}};
  const stage={getMainWindow:async()=>{acquisition++;if(pending)return pending;if(failAcquire)throw {code:1300005};return main;}};
  const scope={window,deviceInfo,hilog:{info:(_d,_t,_f,s)=>logs.push(s)},PalStorage:{errorCode:e=>e.code?'（错误 '+e.code+'）':''},setTimeout:(cb)=>{timers.set(++timerId,cb);return timerId;},clearTimeout:id=>timers.delete(id)};
  vm.createContext(scope);vm.runInContext(code+'\nthis.Policy=PhoneOrientation;',scope);
  const Policy=scope.Policy;
  Policy.install(ability);const policy=Policy.getCurrent();policy.setReporter(m=>reports.push(m));
  assert.notEqual(lifecycle, policy); // SDK callback is a typed adapter, not class inheritance.
  const callbackNames=['onAbilityCreate','onWindowStageCreate','onWindowStageActive','onWindowStageInactive','onWindowStageDestroy','onAbilityDestroy','onAbilityForeground','onAbilityBackground','onAbilityContinue'];
  assert.deepEqual(Object.keys(lifecycle).sort(),callbackNames.sort());
  lifecycle.onAbilityCreate(ability);lifecycle.onAbilityBackground(ability);
  lifecycle.onAbilityContinue(ability);lifecycle.onWindowStageInactive(ability,stage);
  policy.refresh();assert.equal(acquisition,0); // Page may precede stage notification.
  lifecycle.onWindowStageCreate({},stage);assert.equal(acquisition,0); // Another Ability is ignored.
  lifecycle.onWindowStageCreate(ability,stage);policy.refresh();await tick();
  assert.equal(acquisition,1);assert.equal(bindings,1);assert.equal(calls,1);
  assert(logs.some(s=>s.includes('type=1 size=1280x2832')));
  listener(1);await tick();listener(2);await tick();assert.equal(calls,3);
  policy.setReporter(undefined);lifecycle.onAbilityForeground(ability);await tick();assert.equal(calls,4); // UI disappearance does not stop policy.
  policy.setReporter(m=>reports.push(m));failApply=true;listener(2);await tick();assert(reports.at(-1).includes('1300002'));failApply=false;
  const runRetry=async()=>{assert(timers.size);const [id,cb]=timers.entries().next().value;timers.delete(id);cb();await tick();};
  await runRetry();assert.equal(reports.at(-1),'');
  lifecycle.onWindowStageDestroy(ability,stage);assert.equal(detached,1);
  failAcquire=true;lifecycle.onWindowStageCreate(ability,stage);await tick();assert(reports.at(-1).includes('getMainWindow'));assert(reports.at(-1).includes('1300005'));
  await runRetry();await runRetry();await runRetry();assert.equal(timers.size,0); // Bounded startup retries.
  failAcquire=false;lifecycle.onAbilityForeground(ability);await tick();assert.equal(bindings,2); // Resume restores exhausted binding.
  lifecycle.onWindowStageDestroy(ability,stage);failListen=true;lifecycle.onWindowStageCreate(ability,stage);await tick();assert(reports.at(-1).includes('listen windowEvent'));
  failListen=false;await runRetry();assert.equal(bindings,3);
  // A superseded stage's outstanding result must not reset the new binding state.
  lifecycle.onWindowStageDestroy(ability,stage);let resolve;pending=new Promise(r=>resolve=r);lifecycle.onWindowStageCreate(ability,stage);
  lifecycle.onWindowStageDestroy(ability,stage);pending=undefined;
  const nextStage={getMainWindow:stage.getMainWindow};lifecycle.onWindowStageCreate(ability,nextStage);await tick();const bound=bindings;
  resolve(main);await tick();assert.equal(bindings,bound);
  lifecycle.onWindowStageDestroy(ability,stage); // Stale destroy is ignored.
  const before=calls;lifecycle.onAbilityForeground(ability);await tick();assert.equal(calls,before+1);
  lifecycle.onAbilityDestroy(ability);await tick();assert.equal(unregistrations,1);assert.equal(timers.size,0);assert.equal(Policy.getCurrent(),undefined);
  const stopped=calls;policy.refresh();listener(1);await tick();assert.equal(calls,stopped);
  for(const type of ['2in1','tv','default']){deviceInfo.deviceType=type;Policy.install(ability);assert.equal(Policy.getCurrent(),undefined);assert.equal(registrations,1);}
  // Tablet shares the exact same launch and foreground policy as phone.
  deviceInfo.deviceType='tablet';Policy.install(ability);assert(Policy.getCurrent());
  const tabletBefore=calls;lifecycle.onWindowStageCreate(ability,stage);await tick();assert.equal(calls,tabletBefore+1);
  lifecycle.onAbilityForeground(ability);await tick();assert.equal(calls,tabletBefore+2);
  Policy.getCurrent().stop();await tick();
  deviceInfo.deviceType='phone';pending=new Promise(r=>resolve=r);Policy.install(ability);const late=Policy.getCurrent();lifecycle.onWindowStageCreate(ability,stage);late.stop();const count=bindings;resolve(main);await tick();assert.equal(bindings,count);
  // Unregistration may throw synchronously or return a rejected Promise. Neither
  // may leave current set or break the next install before SDL startup.
  pending=undefined;
  for (const synchronous of [true,false]) {
    app.off=(type,id)=>{assert.equal(id,9);if(synchronous)throw {code:401};return Promise.reject({code:401});};
    Policy.install(ability);const failingStop=Policy.getCurrent();
    assert.doesNotThrow(()=>failingStop.stop());
    assert.equal(Policy.getCurrent(),undefined);await tick();
    assert.doesNotThrow(()=>Policy.install(ability));
    const replacement=Policy.getCurrent();assert(replacement);
    // install also calls the previous instance's stop before replacing it.
    assert.doesNotThrow(()=>Policy.install(ability));
    assert.notEqual(Policy.getCurrent(),replacement);
    Policy.getCurrent().stop();await tick();
    assert.equal(Policy.getCurrent(),undefined);
  }
  console.log('Orientation lifecycle regression passed: stage identity, cold start, foreign ability, resume, UI detach, bounded retries, acquisition/listener/apply failures, stale stage, stop, tablet apply/PC skip, late result');
})().catch(e=>{console.error(e);process.exitCode=1;});
