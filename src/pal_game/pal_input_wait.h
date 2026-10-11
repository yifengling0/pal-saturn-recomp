#pragma once
// Experimental field-only scheduler rephasing. Never skip the counter==1
// erase stage or write a negative value. Shared non-field waits stay untouched.
inline int pal_input_wake_target(int current,int interval,bool in_field_wait,
                                 bool pending,bool ready,bool dma_complete) {
    return in_field_wait && pending && ready && dma_complete && interval==6 && current>1 ? 1 : current;
}
inline int pal_input_align_target(int current,bool step) {
    return step && current>2 ? 2 : current;
}
