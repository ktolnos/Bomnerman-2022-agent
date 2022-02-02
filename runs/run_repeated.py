import os
import subprocess
import time
from collections import Counter
from multiprocessing import Pool


def run_command(run_id: int):
    print("Running ", run_id)
    suffix = "{0}-{1}".format(run_id, time.time())
    dir_name = "out/run-" + suffix
    if run_id % 6 == 0:
        subprocess.Popen("docker network prune -f", shell=True).wait()
    subprocess.Popen("mkdir -p " + dir_name +
                     " && cp template/base-compose.yml " + dir_name + "/base-compose.yml" +
                     " && cp template/docker-compose.yml " + dir_name + "/docker-compose.yml"
                     , shell=True).wait()

    with open(dir_name + '/docker-compose.yml', 'r') as file:
        filedata = file.read()

    # Replace the target string
    filedata = filedata.replace('{{PORT}}', str(3010 + run_id))

    # Write the file out again
    with open(dir_name + '/docker-compose.yml', 'w') as file:
        file.write(filedata)

    replay_suffix = suffix + "-" + str(time.time())

    print("Launching the game ", run_id)
    with open(dir_name + '/logs.txt', 'x') as file:
        subprocess.Popen("docker-compose -f " + dir_name +
                         "/docker-compose.yml up --abort-on-container-exit --force-recreate --build",
                         shell=True, stdout=file).wait()
    print("Game ended ", run_id)

    subprocess.Popen("cp " + dir_name + "/logs/replay.json arxiv/replay-" + replay_suffix + ".json" +
                     "&& cp arxiv/replay-" + replay_suffix + ".json tmp/replay-" + replay_suffix + ".json"
                     , shell=True).wait()
    print("Finished ", run_id)

def main():
    subprocess.Popen("rm -rf tmp && mkdir tmp", shell=True).wait()
    pool = Pool(6)
    pool.map(run_command, range(1500))
    score = Counter()
    for filename in os.listdir('tmp'):
        with open("tmp/" + filename, 'r') as file:
            filedata = file.read()
            template = '"winning_agent_id":"'
            idx = filedata.find(template)
            won = filedata[idx + len(template):idx + len(template) + 1]
            if won != 'a':
                print("Lost run " + filename)
            score[won] += 1
    print(score)


if __name__ == "__main__":
    main()
