#!/bin/bash
# Regenerate all 7 seed images via Replicate with golden hour style.
set -e
cd "$(dirname "$0")/.."

TOKEN=$(grep REPLICATE_API_TOKEN .env | cut -d= -f2)
STYLE="golden hour warm light, amber and orange tones, sun low on horizon, long soft shadows, National Geographic editorial style, subject fills frame, sharp focus on animal, cinematic depth of field, emotionally warm mood, no humans, no text, no enclosures, photorealistic"
NEG="cartoon, illustration, watermark, text, logo, cage, fence, captivity, dead, injured, humans, blue tones, cool color grade, harsh midday light, black and white, desaturated, aerial view, blurry subject, dark or moody atmosphere"

SUBJECTS=(
  "eastern barred bandicoot marsupial australia"
  "blue and yellow macaw ara ararauna rainforest"
  "grey wolf pack snowy forest"
  "northern bald ibis rocky cliff habitat"
  "jaguar panthera onca cloud forest"
  "regent honeyeater perched eucalyptus branch"
  "atlantic puffin colony sea cliff nesting"
)

echo "Submitting 7 generation jobs..."
declare -a IDS
for i in "${!SUBJECTS[@]}"; do
  POST=$((i+1))
  PROMPT="Wildlife photography, ${SUBJECTS[$i]}, natural habitat, ${STYLE}"
  ID=$(curl -s -X POST "https://api.replicate.com/v1/models/stability-ai/sdxl/predictions" \
    -H "Authorization: Token $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"input\":{\"prompt\":\"${PROMPT}\",\"negative_prompt\":\"${NEG}\",\"width\":1024,\"height\":1024}}" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id','ERROR:'+str(d)))")
  IDS[$i]=$ID
  echo "  post-$POST submitted: $ID"
done

echo ""
echo "Polling for completion (this takes ~30-60 seconds each)..."
for i in "${!IDS[@]}"; do
  POST=$((i+1))
  ID="${IDS[$i]}"
  echo -n "  post-$POST ($ID)..."
  while true; do
    RESULT=$(curl -s "https://api.replicate.com/v1/predictions/$ID" \
      -H "Authorization: Token $TOKEN")
    STATUS=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))")
    if [ "$STATUS" = "succeeded" ]; then
      URL=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['output'][0])")
      curl -sL "$URL" -o "output/seed/post-$POST/image.jpg"
      sips -z 1080 1080 "output/seed/post-$POST/image.jpg" > /dev/null 2>&1
      echo " done."
      break
    elif [ "$STATUS" = "failed" ]; then
      echo " FAILED."
      break
    else
      echo -n "."
      sleep 5
    fi
  done
done

echo ""
echo "All done. Images saved to output/seed/post-1 through post-7."
