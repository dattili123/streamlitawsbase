(cat "$SCRIPTPATH/output.txt") | mailx -v \
    -s "GitLab Sandbox Conflict Checks Report - $(date +'%m-%d-%Y')" \
    -a "$html_file" \
    -r "flexdeploy_sandbox@cms.hhs.gov" \
    -S smtp="smtp-hgl-smtp-relay.vdcunix.local" \
    "$receivers" \
    >> "$SCRIPTPATH/mail_debug.log" 2>&1

# Check if mailx succeeded and log a message
if [ $? -ne 0 ]; then
    echo "$(date): ERROR - Email to $receivers failed" >> "$SCRIPTPATH/mail_debug.log"
else
    echo "$(date): SUCCESS - Email sent to $receivers" >> "$SCRIPTPATH/mail_debug.log"
fi