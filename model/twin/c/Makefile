# Body Twin host build (B3). Flags per ARCHITECTURE 4.5 / B3 brief.
CC      ?= gcc
CFLAGS  = -std=c99 -O2 -Wall -Wextra -Werror -Wdouble-promotion -fsingle-precision-constant -ffp-contract=off -Wshadow -Wconversion -Wno-sign-conversion
LDLIBS  = -lm

all: host_test

host_test: host_test.c hg_twin.c hg_twin.h
	$(CC) $(CFLAGS) -o $@ host_test.c hg_twin.c $(LDLIBS)

test: host_test
	./host_test ../tests

# same test compiled against B5's guardian/c/hg2_step.h (shared hg2_twin_t / hg2_in_t)
test-hg2: host_test.c hg_twin.c hg_twin.h
	$(CC) $(CFLAGS) -DHG_TWIN_USE_HG2_STEP_H -I../../guardian/c -o host_test_hg2 host_test.c hg_twin.c $(LDLIBS)
	./host_test_hg2 ../tests

# golden nights from 10 SIM-DEV persons (needs model/sealed_hg2.json + sim/data/minutes_dev.parquet)
test-sim: host_test
	cd ../tests && python3 make_golden.py --source sim --prefix golden_sim
	./host_test ../tests golden_sim

# DECISIONS M4.3 sourced reading mode + gap-gain rule variants, each with its own golden set
test-krules: host_test.c hg_twin.c hg_twin.h
	cd ../tests && python3 make_golden.py --reading-mode 1 --prefix golden_sourced >/dev/null && python3 make_golden.py --reading-mode 1 --k-rule 1 --prefix golden_keff >/dev/null && python3 make_golden.py --reading-mode 1 --k-rule 2 --prefix golden_koff >/dev/null
	$(CC) $(CFLAGS) -DHG_TWIN_READING_MODE=1 -o host_test_sourced host_test.c hg_twin.c $(LDLIBS) && ./host_test_sourced ../tests golden_sourced
	$(CC) $(CFLAGS) -DHG_TWIN_READING_MODE=1 -DHG_TWIN_K_RULE=1 -o host_test_keff host_test.c hg_twin.c $(LDLIBS) && ./host_test_keff ../tests golden_keff
	$(CC) $(CFLAGS) -DHG_TWIN_READING_MODE=1 -DHG_TWIN_K_RULE=2 -o host_test_koff host_test.c hg_twin.c $(LDLIBS) && ./host_test_koff ../tests golden_koff

# no expf/logf/powf/malloc in the band code
check-symbols: hg_twin.c
	$(CC) $(CFLAGS) -c -o hg_twin.o hg_twin.c
	@! nm hg_twin.o | grep -E ' U (expf|logf|powf|exp|log|pow|malloc|calloc|free|realloc)$$' && echo "symbols OK: no exp/log/pow/malloc"
	@nm hg_twin.o | grep ' U ' || true
	@size hg_twin.o

clean:
	rm -f host_test host_test_hg2 host_test_sourced host_test_keff host_test_koff hg_twin.o
.PHONY: all test clean check-symbols
