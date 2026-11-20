/* T6a: the libc behaviour behind 08_logger's handleCommand() on edge inputs (same calls as the sketch). */
#include <stdio.h>
#include <stdlib.h>
#include <ctype.h>
#include <math.h>
int main(void){
  const char *oral[]={"36.85","36,85","3685","abc","36.855"};
  for(int i=0;i<5;i++){float t=atof(oral[i]); int ok=!(t<30.0f||t>43.0f); printf("mark oral %-7s -> atof=%.3f accepted=%d stored_x100=%ld\n",oral[i],t,ok,ok?lroundf(t*100.0f):-1L);}
  const char *tm[]={"1763287200","1763287200abc","-1","17632872000","0x69000000"," 1763287200"};
  for(int i=0;i<6;i++){unsigned long u=strtoul(tm[i],NULL,10); printf("time %-13s -> %lu accepted=%d\n",tm[i],u,!(u<1700000000UL||u>4000000000UL));}
  const char *mk[]={"1x","07","-1","9999999999"};
  for(int i=0;i<4;i++){int m=-1; if(isdigit((unsigned char)mk[i][0])) m=atoi(mk[i]); printf("mark %-10s -> m=%d accepted=%d\n",mk[i],m,m>=1&&m<=9);}
  return 0;}
