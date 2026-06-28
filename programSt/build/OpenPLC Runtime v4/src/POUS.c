void MAIN_init__(MAIN *data__, BOOL retain) {
  __INIT_LOCATED(INT,__MW0,data__->OUTPUT,retain)
  __INIT_LOCATED_VALUE(data__->OUTPUT,0)
}

// Code part
void MAIN_body__(MAIN *data__) {
  // Initialise TEMP variables

  __SET_LOCATED(data__->,OUTPUT,,(__GET_LOCATED(data__->OUTPUT,) + 1));

  goto __end;

__end:
  return;
} // MAIN_body__() 





