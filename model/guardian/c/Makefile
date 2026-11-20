# Heat Guardian guardian/c host build.  make test | make replay IN=.. OUT=.. | make stack | make ref
CC      ?= gcc
CFLAGS  = -std=c99 -Wall -Wextra -Werror -Wdouble-promotion -fsingle-precision-constant -O2 -ffp-contract=off
# B2's trained export wins when it exists; otherwise the random STUB weights (HG2_WEIGHTS_STUB = 1)
WDIR    := $(if $(wildcard ../../model/export/hg2_weights.h),../../model/export,stub)
SRC     = hg_util.c hg_tables.c hg_kf.c hg2_step.c hg_contact.c hg_homeout.c hg_routine.c hg_frames.c hg_guardian.c $(WDIR)/hg2_weights.c
HDR     = $(wildcard *.h) $(WDIR)/hg2_weights.h
BIN     = build

all: $(BIN)/host_test

$(BIN)/host_test: $(SRC) host_test.c $(HDR)
	@mkdir -p $(BIN)
	$(CC) $(CFLAGS) -I. -I$(WDIR) host_test.c $(SRC) -lm -o $@

# M11.5 guardian <-> Body Twin (B3) integration
TWIN    = ../../twin/c
$(BIN)/twin_integration: ../tests/twin_integration.c hg_guardian_twin.c $(SRC) $(HDR) $(TWIN)/hg_twin.c $(TWIN)/hg_twin.h
	@mkdir -p $(BIN)
	$(CC) $(CFLAGS) -DHG_TWIN_USE_HG2_STEP_H -I. -I$(WDIR) -I$(TWIN) ../tests/twin_integration.c hg_guardian_twin.c $(SRC) $(TWIN)/hg_twin.c -lm -o $@

test: $(BIN)/host_test $(BIN)/twin_integration
	@echo "weights: $(WDIR)"
	python3 ../tests/make_vectors.py
	cd $(BIN) && ./host_test ../../tests
	$(BIN)/twin_integration

# stack usage: per-function frames + call graph (GCC -fcallgraph-info=su), summed by ../py/stack_highwater.py
stack: $(SRC) host_test.c
	@mkdir -p $(BIN)/su
	cd $(BIN)/su && for f in $(SRC); do $(CC) $(CFLAGS) -fstack-usage -fcallgraph-info=su -I../.. -I../../$(WDIR) -c ../../$$f; done
	python3 ../py/stack_highwater.py $(BIN)/su hg_guardian_step

# B5-v7: every screen text's glyphs exist in the 09 firmware font (u8g2_font_10x20_t_greek) + the «βραχιόλι» spelling fix
U8G2    = /root/Arduino/libraries/U8g2/src/clib
glyph: ../tests/glyph_check.c $(SRC) $(HDR)
	@mkdir -p $(BIN)
	$(CC) -std=c99 -O1 -w -I$(U8G2) -I. -I$(WDIR) ../tests/glyph_check.c $(U8G2)/*.c $(SRC) -lm -o $(BIN)/glyph_check
	$(BIN)/glyph_check

# v1.2 reference comparison binary (includes /home/claude/hgmodel/heat_guardian_band.c read-only)
$(BIN)/ref_v12: ../tests/ref_v12.c hg_kf.c hg_util.c hg_tables.c $(HDR)
	@mkdir -p $(BIN)
	$(CC) -std=c99 -O2 -ffp-contract=off -fsingle-precision-constant -Wall -Wextra -Wno-unused-function -I. ../tests/ref_v12.c hg_kf.c hg_util.c hg_tables.c -lm -o $@
ref: $(BIN)/ref_v12

clean:
	rm -rf $(BIN)
.PHONY: all test stack ref clean
