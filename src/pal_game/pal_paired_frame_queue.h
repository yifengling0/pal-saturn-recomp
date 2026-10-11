#pragma once
#include "saturn/sh2.h"
extern bool pal_pfq_enabled;
extern int pal_pfq_host_bank;
extern uint16_t pal_pfq_host_tvmr;
struct Frame;
void pal_pfq_field_begin(const SH2Context&);
void pal_pfq_master_seal();
void pal_pfq_slave_done();
void pal_pfq_clear(const char*);
void pal_pfq_dma_begin(int,uint32_t,uint32_t,uint32_t,uint32_t,uint32_t);
void pal_pfq_dma_end(int);
void pal_pfq_draw_begin(int,uint64_t,const uint16_t*);
void pal_pfq_sprite_end();
void pal_pfq_bank_invalidate(int,const char*);
bool pal_pfq_choose(Frame&,int,const uint16_t*,bool);
bool pal_pfq_compose_frame(Frame&);
