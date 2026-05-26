#!/bin/bash
# INGInious documentation : https://docs.inginious.org/en/latest/teacher_doc/run_file.html

##################################################
# ========== CONFIG (EDIT THIS PART) ==========
##################################################


VARIATIONS_PATH="/task/corrections"
ORIGINAL_LAB_CONF="/task/originalLab.conf"
CSV_ANALYZER="/task/extractFeedbackFromCSV.py"
BASE_DOWNLOAD_URL="https://inginious.info.ucl.ac.be/course/tfe-vanhorenbeke/ospf-shortestpath/variations"
FEEDBACK_TEMPLATE="feedbackTable"
TASK_ID_UPLOAD="studentupload"

##################################################
# ==============================================
##################################################

username=$(getinput @username)
if [ -z "$username" ]; then
    username="etudiant_inconnu"
fi

mapfile -t files < <(find "$VARIATIONS_PATH" -maxdepth 1 -name "*.yaml" -type f -printf "%f\n" 2>/dev/null | sort)

if [ ${#files[@]} -eq 0 ]; then
    echo "Erreur: Aucune variante de yaml dans $VARIATIONS_PATH" | feedback-msg -ae
    feedback-result failed
    exit 1
fi

nb_variantes=${#files[@]}

variant_index=$(python3 - <<EOF
from inginious import input as inginious_input
rand = inginious_input.get_input("@random")[0]
print(int(rand * $nb_variantes))
EOF
)

selected_correction_yaml="correction_admin_$variant_index.yaml"
selected_zip="variant_$variant_index.zip"

ROOT_DIR=$(pwd)

touch ./logs

### Get student zip ###
FILENAME=$(getinput "$TASK_ID_UPLOAD":filename)
getinput "$TASK_ID_UPLOAD" > student/uploaded_file

if [ "$FILENAME" != "$selected_zip" ]; then
    echo "❌ Wrong file submitted! \n" | feedback-msg -ae
    echo "Expected file: $selected_zip \n" | feedback-msg -ae
    echo "Submitted file: $FILENAME \n" | feedback-msg -ae
    echo "Your ZIP is available here : $BASE_DOWNLOAD_URL/$selected_zip \n" | feedback-msg -ae
    feedback-result failed
    exit 1
fi

if [[ "$FILENAME" == *.zip ]]; then
    unzip -l student/uploaded_file
    unzip student/uploaded_file -d student/unzipped

    if [ -d "student/unzipped" ]; then
        LAB_PATH="student/unzipped/"
    else
        echo "Folder was not found at the root of the zip." | feedback-msg -a
        feedback-result failed
        exit 1
    fi

    cd "$LAB_PATH"
    find . -maxdepth 1 -type f \( -name "*result_all.csv" \
        -o -name "*results_failed.csv" \
        -o -name "*summary*.csv" \) -delete

    cp -f "$ORIGINAL_LAB_CONF" ./lab.conf

    stdbuf -oL -eL python3 -m kathara_lab_checker --config "$VARIATIONS_PATH/$selected_correction_yaml" --no-cache --lab "$(pwd)" &>> ./logs

else
    echo "You must submit a .zip file" | feedback-msg -a
    feedback-result failed
    exit 1
fi

##################################################
# === PARSING LOGS ===
##################################################

TOTAL_TESTS=$(grep "Total Tests:" ./logs | tail -1 | grep -o '[0-9]\+')
PASSED_TESTS=$(grep "Passed Tests:" ./logs | tail -1 | grep -o '[0-9]\+/[0-9]\+' | cut -d'/' -f1)
FAILED_TESTS=$((TOTAL_TESTS - PASSED_TESTS))

GRADE=$(echo "scale=2; ($PASSED_TESTS / $TOTAL_TESTS) * 100" | bc)

echo "Grade: $GRADE%" | feedback-msg -a
echo "Total Tests: $TOTAL_TESTS" | feedback-msg -a
echo "Passed Tests: $PASSED_TESTS/$TOTAL_TESTS" | feedback-msg -a

feedback-grade $GRADE

##################################################
# === CSV ANALYSIS ===
##################################################

CUSTOM_COMMENT=""

FAILED_CSV=$(find "$(pwd)" -maxdepth 1 -type f -name "*result_all.csv" \
    -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2-)

if [ -n "$FAILED_CSV" ] && [ -f "$FAILED_CSV" ]; then
    TESTS_DATA=$(python3 "$CSV_ANALYZER" "$FAILED_CSV" 2>> ./logs)
    TESTS_DATA=$(echo "$TESTS_DATA" | sed ':a;N;$!ba;s/\n/\\n/g')
    CUSTOM_COMMENT="You can download your archive here : $BASE_DOWNLOAD_URL/$selected_zip"
else
    CUSTOM_COMMENT="No CSV found in $(pwd)"
fi

cd "$ROOT_DIR"


feedback-msg-tpl "$FEEDBACK_TEMPLATE" \
    score="$GRADE" \
    passed="$PASSED_TESTS" \
    failed="$FAILED_TESTS" \
    time="$ELAPSED" \
    tests_data="$TESTS_DATA" \
    total_tests="$TOTAL_TESTS" \
    comment=""

if [ -n "$CUSTOM_COMMENT" ]; then
    echo "$CUSTOM_COMMENT" | feedback-msg -a
fi

if [ "$PASSED_TESTS" -eq "$TOTAL_TESTS" ]; then
    feedback-result success
else
    feedback-result failed
fi