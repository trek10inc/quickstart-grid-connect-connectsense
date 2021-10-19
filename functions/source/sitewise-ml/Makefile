# Used by SAM build process to package shared scripts into
# layer accessible by other functions

build-MLSharedLibraries:
	$(eval LIBRARY_DIR = $(ARTIFACTS_DIR)/python/shared/)
	rm -rf ${LIBRARY_DIR}
	mkdir -p ${LIBRARY_DIR}
	cp *.py ${LIBRARY_DIR}
	pip download -r requirements.txt -d $(ARTIFACTS_DIR)/python
