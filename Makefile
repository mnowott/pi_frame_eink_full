MODULES := eInkFrameWithStreamlitMananger \
           pi-s3-sync \
           s3_image_croper_ui_app/ImageUiApp \
           s3_image_croper_ui_app/SettingsApp

.PHONY: check install lint typecheck format format-check doctest test coverage

check: lint typecheck format-check test

install:
	@for mod in $(MODULES); do echo "=== install $$mod ===" && $(MAKE) -C $$mod install || exit 1; done

lint:
	@for mod in $(MODULES); do echo "=== lint $$mod ===" && $(MAKE) -C $$mod lint || exit 1; done

typecheck:
	@for mod in $(MODULES); do echo "=== typecheck $$mod ===" && $(MAKE) -C $$mod typecheck || exit 1; done

format:
	@for mod in $(MODULES); do echo "=== format $$mod ===" && $(MAKE) -C $$mod format || exit 1; done

format-check:
	@for mod in $(MODULES); do echo "=== format-check $$mod ===" && $(MAKE) -C $$mod format-check || exit 1; done

doctest:
	@for mod in $(MODULES); do echo "=== doctest $$mod ===" && $(MAKE) -C $$mod doctest || exit 1; done

test:
	@for mod in $(MODULES); do echo "=== test $$mod ===" && $(MAKE) -C $$mod test || exit 1; done

coverage:
	@for mod in $(MODULES); do echo "=== coverage $$mod ===" && $(MAKE) -C $$mod coverage || exit 1; done
