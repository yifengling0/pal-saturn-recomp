const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {stripTypeScriptTypes} = require('node:module');
const code = stripTypeScriptTypes(fs.readFileSync(process.argv[2], 'utf8').replace(/^import .*;\n/gm, ''), {mode:'transform'}).replace('export class', 'class');
let listener, applications=0, foldable=false, status=3;
const timers=new Map(), updates=[];let id=0;
const events=new Map();
const main={on:(name,callback)=>events.set(name,callback),off:(name)=>events.delete(name),
  getWindowProperties:()=>({displayId:1,windowRect:{left:0,top:0}})};
const screen={id:1,rotation:0,getLiveCreaseRegion:()=>({displayId:1,creaseRects:[{left:0,top:780,width:2560,height:40}]})};
const scope={window:{Orientation:{AUTO_ROTATION_LANDSCAPE:7,AUTO_ROTATION_PORTRAIT:6,AUTO_ROTATION:5}},
  display:{isFoldable:()=>foldable,getFoldStatus:()=>status,getDefaultDisplaySync:()=>screen,getDisplayByIdSync:()=>screen,
    on:(name,callback)=>events.set(name,callback),off:(name)=>events.delete(name)},
  deviceInfo:{sdkApiVersion:20},hilog:{info:()=>{}},
  palDisplay:{update:(half,rectangles)=>updates.push({half,rectangles}),onOrientationChange:callback=>{listener=callback;if(callback)callback(0);}},
  setTimeout:callback=>{timers.set(++id,callback);return id;},clearTimeout:key=>timers.delete(key)};
vm.createContext(scope);vm.runInContext(code+'\nthis.Adapter=FoldLayout;',scope);
const adapter=new scope.Adapter();
adapter.bind(main,()=>applications++);
assert.equal(applications,1);assert.equal(adapter.preferredOrientation(),7);
listener(1);assert.equal(adapter.preferredOrientation(),6);
listener(2);assert.equal(adapter.preferredOrientation(),5);
assert.equal(applications,3);
assert(events.has('windowSizeChange')); // Ordinary tablets also observe rotation/resizing.
foldable=true;adapter.setSurface(0,0,2560,1600);
const flush=()=>{for(const [key,callback] of [...timers]){timers.delete(key);callback();}};
flush();assert.equal(updates.at(-1).half,true);
assert.equal(updates.at(-1).rectangles.length,4);
listener(0);assert.equal(adapter.preferredOrientation(),7); // Half-fold does not override explicit direction.
events.get('windowSizeChange')({width:1600,height:2560});
assert.equal(updates.at(-1).half,false); // Do not reuse old crease geometry after rotation.
adapter.stop();assert.equal(listener,undefined);assert.equal(events.size,0);assert.equal(timers.size,0);
console.log('Screen direction events, half-fold preference, resize invalidation and cleanup passed');
