import os
import subprocess
import time
from collections import Counter
from multiprocessing import Pool


def run_command(run_id: int):
    print("Running ", run_id)
    suffix = "{0}-{1}".format(run_id, time.time())
    dir_name = "out/run-" + suffix
    subprocess.Popen("mkdir -p " + dir_name +
                     " && cp template/base-compose.yml " + dir_name + "/base-compose.yml" +
                     " && cp template/docker-compose.yml " + dir_name + "/docker-compose.yml"
                     , shell=True).wait()
    subprocess.Popen("mkdir -p " + dir_name + "/agents && touch " + dir_name + "/agents/replay.json",
                         shell=True).wait()

    with open(dir_name + '/docker-compose.yml', 'r') as file:
        filedata = file.read()

    # Replace the target string
    filedata = filedata.replace('{{PORT}}', str(4000 + run_id))

    # Write the file out again
    with open(dir_name + '/docker-compose.yml', 'w') as file:
        file.write(filedata)

    replay_suffix = suffix + "-" + str(time.time())

    launch_game_command = "docker-compose -f " + dir_name + "/docker-compose.yml up --abort-on-container-exit " \
                                                            "--build "
    print("Launching the game ", run_id, "\n", launch_game_command)
    with open(dir_name + '/logs.txt', 'x') as file:
        subprocess.Popen(launch_game_command,
                         shell=True, stdout=file).wait()
    print("Game ended ", run_id)

    subprocess.Popen("cp " + dir_name + "/agents/replay.json tmp/replay-" + replay_suffix + ".json"
                     , shell=True).wait()

    subprocess.Popen("docker network rm run-" + suffix.replace(".", "") + "_coderone-tournament", shell=True).wait()
    print("Finished ", run_id)


def main():
    print(os.getcwd())
    started = time.time()
    subprocess.Popen("rm -rf tmp && mkdir tmp", shell=True).wait()
    pool = Pool(12)
    pool.map(run_command, range(120))
    score = Counter()
    for filename in os.listdir('tmp'):
        with open("tmp/" + filename, 'r') as file:
            filedata = file.read()
            template = '"winning_agent_id":"'
            idx = filedata.find(template)
            won = filedata[idx + len(template):idx + len(template) + 1]
            if won == 'a':
                print("Lost run " + filename)
            score[won] += 1
    print(score)
    print("Time = {}s".format(
        (time.time() - started)
    ))


if __name__ == "__main__":
    main()
