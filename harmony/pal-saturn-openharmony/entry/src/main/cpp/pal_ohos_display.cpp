#include "pal_ohos_display.h"
#include <napi/native_api.h>
#include <mutex>

namespace {
std::mutex mutex;
pal_display::Fold current;
int orientation=0;
napi_threadsafe_function orientation_listener=nullptr;

void orientation_callback(napi_env env,napi_value callback,void*,void*) {
    if(!env||!callback)return;
    int value;
    {std::lock_guard<std::mutex> lock(mutex);value=orientation;}
    napi_value argument,receiver,result;
    napi_create_int32(env,value,&argument);
    napi_get_undefined(env,&receiver);
    napi_call_function(env,receiver,callback,1,&argument,&result);
}
void clear_orientation_listener(void*) {
    std::lock_guard<std::mutex> lock(mutex);
    if(orientation_listener)napi_release_threadsafe_function(orientation_listener,napi_tsfn_abort);
    orientation_listener=nullptr;
}
napi_value on_orientation_change(napi_env env,napi_callback_info info) {
    size_t argc=1;
    napi_value callback,result;
    napi_get_cb_info(env,info,&argc,&callback,nullptr,nullptr);
    napi_valuetype type=napi_undefined;
    if(argc)napi_typeof(env,callback,&type);
    if(type!=napi_function&&type!=napi_undefined) {
        napi_throw_type_error(env,nullptr,"Expected an orientation callback or undefined");
        return nullptr;
    }
    clear_orientation_listener(nullptr);
    if(type==napi_function) {
        napi_value name;
        napi_create_string_utf8(env,"PAL screen orientation",NAPI_AUTO_LENGTH,&name);
        napi_threadsafe_function listener=nullptr;
        if(napi_create_threadsafe_function(env,callback,nullptr,name,1,1,nullptr,nullptr,
                                          nullptr,orientation_callback,&listener)!=napi_ok) {
            napi_throw_error(env,nullptr,"Cannot register the window orientation callback");
            return nullptr;
        }
        napi_unref_threadsafe_function(env,listener);
        {std::lock_guard<std::mutex> lock(mutex);orientation_listener=listener;}
        // Read the latest request when invoked, so a full queue coalesces rapid changes.
        orientation_callback(env,callback,nullptr,nullptr);
    }
    napi_get_undefined(env,&result);
    return result;
}
napi_value update(napi_env env,napi_callback_info info) {
    napi_value args[2],result;
    size_t argc=2;
    napi_get_cb_info(env,info,&argc,args,nullptr,nullptr);
    pal_display::Fold next{};
    bool array=false;
    uint32_t length=0;
    if(argc!=2||napi_get_value_bool(env,args[0],&next.half)!=napi_ok||
       napi_is_array(env,args[1],&array)!=napi_ok||!array||
       napi_get_array_length(env,args[1],&length)!=napi_ok||length>16||length%4!=0) {
        napi_throw_type_error(env,nullptr,"Expected half-fold boolean and up to four normalized rectangles");
        return nullptr;
    }
    next.count=(int)length/4;
    for(int i=0;i<next.count;++i) {
        float* fields[]={&next.creases[i].x,&next.creases[i].y,&next.creases[i].w,&next.creases[i].h};
        for(int j=0;j<4;++j) {
            napi_value value;double number=0;
            if(napi_get_element(env,args[1],i*4+j,&value)!=napi_ok||
               napi_get_value_double(env,value,&number)!=napi_ok||!std::isfinite(number)||number<0||number>1) {
                napi_throw_range_error(env,nullptr,"Crease coordinates must be finite values in 0..1");
                return nullptr;
            }
            *fields[j]=(float)number;
        }
    }
    {std::lock_guard<std::mutex> lock(mutex);current=next;}
    napi_get_undefined(env,&result);
    return result;
}
napi_value init(napi_env env,napi_value exports) {
    const napi_property_descriptor props[]={
        {"update",nullptr,update,nullptr,nullptr,nullptr,napi_default,nullptr},
        {"onOrientationChange",nullptr,on_orientation_change,nullptr,nullptr,nullptr,napi_default,nullptr}};
    napi_define_properties(env,exports,2,props);
    napi_add_env_cleanup_hook(env,clear_orientation_listener,nullptr);
    return exports;
}
napi_module module={1,0,nullptr,init,"pal_display",nullptr,{nullptr}};
__attribute__((constructor)) void register_module() {napi_module_register(&module);}
}
namespace pal_ohos_display {
pal_display::Fold snapshot() {std::lock_guard<std::mutex> lock(mutex);return current;}
void request_orientation(int value) {
    value=std::clamp(value,0,2);
    std::lock_guard<std::mutex> lock(mutex);
    if(value==orientation)return;
    orientation=value;
    if(orientation_listener)napi_call_threadsafe_function(orientation_listener,nullptr,napi_tsfn_nonblocking);
}
}
