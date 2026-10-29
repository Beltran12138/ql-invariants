for i in 1 2 3 4 5 6; do
  n=$(ls gen | grep -cE '^opus__.*\.raw$')
  echo "$(date -u) iteration $i opus_raw=$n" >> cloud_run_1027/loop.log
  [ "$n" -ge 15 ] && break
  python3 -I gen.py 5 opus >> cloud_run_1027/gen_log.txt 2>&1
  sleep 600
done
echo "$(date -u) loop done opus_raw=$(ls gen | grep -cE '^opus__.*\.raw$')" >> cloud_run_1027/loop.log
