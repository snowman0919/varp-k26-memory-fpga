PYTHON ?= python3
PYTHONPATH := $(CURDIR)/src

.PHONY: setup doctor test model-trace paper-experiments power-cost rtl-test research-reproduce research-freeze \
	kicad-gate figures flows paper presentation animations setup-presentation study publication-index evidence-index \
	reproduce reproduce-paper release source-archive-test github-archive-test \
	clean clean-rtl distclean

setup:
	$(PYTHON) -m pip install -r requirements.txt

setup-presentation:
	$(PYTHON) -m pip install -r requirements-presentation.txt

doctor:
	$(PYTHON) scripts/audit_phase_a_toolchain.py

test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m unittest tests.test_k26_scheduler_model tests.test_power_cost tests.test_repository_contract -v

model-trace:
	@test -n "$(GEMMA3_1B_ONNX_DIR)" || { echo "BLOCKED: set GEMMA3_1B_ONNX_DIR to an authorized local artifact"; exit 2; }
	$(PYTHON) experiments/gemma3_1b/generate_trace.py --model-dir "$(GEMMA3_1B_ONNX_DIR)"
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m unittest experiments.gemma3_1b.tests.test_trace_generator -v

paper-experiments:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) scripts/run_k26_experiments.py

power-cost:
	$(PYTHON) scripts/build_power_cost_evidence.py

rtl-test:
	sbt -batch "testOnly varp.TileSchedulerSpec varp.K26WorkStealingTopSpec varp.MultiChannelMemorySchedulerSpec varp.BundleRouterSpec varp.ComputeClusterSpec varp.LegacyMatVecSpec varp.WorkStealingEvidenceSpec varp.GemmaWeightTileRtlParitySpec"

kicad-gate:
	$(PYTHON) scripts/verify_k26_kicad.py

publication-index:
	$(PYTHON) publication_tools/generate_publication_and_presentation.py
	$(PYTHON) publication_tools/validate_publication_and_presentation.py

figures flows: publication-index

research-reproduce: doctor test rtl-test paper-experiments power-cost kicad-gate publication-index paper evidence-index

research-freeze: research-reproduce
	$(PYTHON) scripts/validate_research_freeze.py

presentation: research-freeze animations
	$(PYTHON) presentation/tools/build_editable_deck.py
	$(PYTHON) presentation/tools/generate_visual_summary.py
	$(PYTHON) presentation/tools/validate_editable_deck.py

animations:
	$(PYTHON) presentation/tools/generate_conference_figures.py
	$(PYTHON) presentation/tools/generate_animations.py

study:
	$(PYTHON) scripts/build_study_pack.py

paper: publication-index
	$(PYTHON) paper/final/build_paper.py

evidence-index:
	$(PYTHON) scripts/build_release.py --index-only

reproduce: research-reproduce
	$(PYTHON) scripts/verify_clean_source.py

reproduce-paper: reproduce

release: reproduce
	$(PYTHON) scripts/build_release.py

source-archive-test:
	$(PYTHON) scripts/test_source_archive.py

github-archive-test:
	$(PYTHON) scripts/test_github_archive.py

clean:
	rm -rf build

clean-rtl:
	rm -rf target project/target project/project simWorkspace

distclean: clean clean-rtl
	rm -f paper/final/*.html paper/final/*_plaintext.txt paper/final/*_pdf_text.txt
	rm -f paper/technical_report/*.html paper/technical_report/*_plaintext.txt paper/technical_report/*_pdf_text.txt
