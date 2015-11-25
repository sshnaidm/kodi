#!/bin/sh

CURDIR=$(dirname $0)
PLUGIN="plugin.video.postnauka"
DEBUG="$1"
echo "Started building..."
if [ "$DEBUG" != "-d" ]; then
echo "Removing debug from settings"
sed -i 's/id="debug_enabled" default="true"/id="debug_enabled" default="false"/' "${CURDIR}/${PLUGIN}/resources/settings.xml"
fi
zip -r "${CURDIR}/${PLUGIN}.zip" "${CURDIR}/${PLUGIN}" -x "*pyo" -x "*/resources/language/*" -x "*.idea/*"
sed -i 's/id="debug_enabled" default="false"/id="debug_enabled" default="true"/' "${CURDIR}/${PLUGIN}/resources/settings.xml"
VERSION=$(cat ${CURDIR}/${PLUGIN}/addon.xml | python -c "import sys,re;sys.stdout.write(re.findall('version=\"([^\"]+)\"', sys.stdin.read())[1])")
zip -r "${CURDIR}/${PLUGIN}-${VERSION}.zip" "${CURDIR}/${PLUGIN}" -x "*pyo" -x "*/resources/language/*" -x "*.idea/*"
echo "Completed!"



