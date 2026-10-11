#pragma once
extern "C" {
void mock_reset();
void mock_online(const char* id, const char* name);
void mock_offline(const char* id);
void mock_button(const char* id,int code,bool down);
void mock_axis(const char* id,int source,double x,double y);
void mock_enum_race(const char* id);
void mock_enum_connect(const char* id);
void mock_late_button(const char* id,int code,bool down);
void mock_fail_registration(int nth);
void mock_fail_enumeration(bool fail);
int mock_registrations();
int mock_allocations();
void mock_block_getter(bool blocked);
bool mock_getter_waiting();
}
