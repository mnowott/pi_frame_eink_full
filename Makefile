MODULES := eInkFrameWithStreamlitMananger \
           pi-s3-sync \
           s3_image_croper_ui_app/ImageUiApp \
           s3_image_croper_ui_app/SettingsApp

.PHONY: check install lint test

check: lint test

install:
	@for mod in $(MODULES); do echo "=== install $$mod ===" && $(MAKE) -C $$mod install || exit 1; done

lint:
	@for mod in $(MODULES); do echo "=== lint $$mod ===" && $(MAKE) -C $$mod lint || exit 1; done

test:
	@for mod in $(MODULES); do echo "=== test $$mod ===" && $(MAKE) -C $$mod test || exit 1; done
