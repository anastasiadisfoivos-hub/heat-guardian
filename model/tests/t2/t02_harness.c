#include <stdio.h>
#include <stdlib.h>
#include "hg2_nn.h"
int main(int argc, char **argv) { (void)argc; FILE *fi = fopen(argv[1], "rb"), *fo = fopen(argv[2], "wb"); float z[32];
  if (!fi || !fo) return 2;
  if (!hg2_nn_check_crc()) return 3;
  while (fread(z, sizeof(float), 32, fi) == 32) { float y[9], mean[9], sd[9];
    for (int k = 0; k < HG2_NN_ENS; k++) { hg2_nn_forward(&HG2_MEMBERS[k], z, y); fwrite(y, sizeof(float), 9, fo); }
    hg2_nn_ensemble(z, mean, sd); fwrite(mean, sizeof(float), 9, fo); fwrite(sd, sizeof(float), 9, fo); }
  fclose(fi); fclose(fo); return 0; }
