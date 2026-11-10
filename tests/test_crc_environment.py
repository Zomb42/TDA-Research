"""Exercise CRC bootstrap/activation with fake module and Conda commands."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class CrcEnvironmentTest(unittest.TestCase):
    def test_missing_credentials_identify_path_without_printing_contents(self):
        for missing in ('json','pem'):
            with self.subTest(missing=missing),tempfile.TemporaryDirectory(prefix='crc-key-test-') as directory:
                root=Path(directory);(root/'market_data').mkdir()
                (root/'market_data/record_btc_archive.py').touch()
                credentials=root/'credentials.json';key=root/'private.pem'
                if missing=='pem':credentials.write_text('SECRET_VALUE_MUST_NOT_BE_LOGGED')
                env={k:v for k,v in os.environ.items() if k!='BASH_ENV' and not k.startswith('BASH_FUNC_')}
                env.update(JOB_ID='123',SGE_O_WORKDIR=str(root),KALSHI_CREDENTIALS=str(credentials),
                           KALSHI_KEY=str(key),CAPTURE_COINBASE='0')
                result=subprocess.run(['/bin/bash',str(ROOT/'jobs/kalshi_btc_crc.job')],
                                      env=env,capture_output=True,text=True)
                self.assertEqual(result.returncode,2,result.stdout+result.stderr)
                self.assertIn(str(credentials if missing=='json' else key),result.stderr)
                self.assertIn('Missing or unreadable credential file',result.stderr)
                self.assertNotIn('SECRET_VALUE_MUST_NOT_BE_LOGGED',result.stdout+result.stderr)
                self.assertFalse((root/'market_data/recordings').exists())

    def test_job_shebang_survives_crc_wrapper_argument_expansion(self):
        job=ROOT/'jobs/kalshi_btc_crc.job'
        # Reproduce the wrapper supplied from crcfe01: USR_SHELL is expanded
        # unquoted after -S. A login flag here becomes a qsub resource flag.
        command='''USR_SHELL=$(grep -s '#!/bin/' "$1" | sed 's/#!//')
capture() { printf '%s\\n' "$@"; }
capture -binding linear_per_task:1 -S $USR_SHELL -v "BASH_ENV=$HOME/.bash_profile" "$1"
'''
        result=subprocess.run(['/bin/bash','-c',command,'crc-wrapper-test',str(job)],
                              capture_output=True,text=True,check=True)
        self.assertEqual(result.stdout.splitlines(),[
            '-binding','linear_per_task:1','-S','/bin/bash','-v',
            'BASH_ENV='+str(Path.home()/'.bash_profile'),str(job)])

    def test_recipe_matches_the_capture_requirements(self):
        recipe=(ROOT/'environment-crc.yml').read_text()
        pins=set(re.findall(r'^\s+- ([\w-]+==\S+)$',recipe,re.MULTILINE))
        requirements={line.strip() for line in (ROOT/'market_data/requirements-capture.txt').read_text().splitlines()
                      if line.strip() and not line.lstrip().startswith('#')}
        self.assertEqual(pins,requirements)

    def test_bootstrap_and_fresh_shell_activation(self):
        for existing in (False,True):
            with self.subTest(existing_tda=existing),tempfile.TemporaryDirectory(prefix='crc-env-test-') as temporary:
                root=Path(temporary);repo=root/'checkout';(repo/'jobs').mkdir(parents=True)
                for name in ('setup_crc.sh','crc_conda.sh'):
                    shutil.copy2(ROOT/'jobs'/name,repo/'jobs'/name)
                shutil.copy2(ROOT/'environment-crc.yml',repo/'environment-crc.yml')
                bin_dir=root/'bin';bin_dir.mkdir()
                (bin_dir/'uname').write_text('#!/bin/bash\necho Linux\n')
                (bin_dir/'uname').chmod(0o700)
                python_stub=bin_dir/'python'
                python_stub.write_text('#!'+sys.executable+'\nimport json,os,sys\n'
                    'with open(os.environ["CRC_TEST_LOG"],"a") as stream: stream.write(json.dumps(sys.argv[1:])+"\\n")\n')
                python_stub.chmod(0o700)
                prefix=root/'conda with spaces';(prefix/'etc/profile.d').mkdir(parents=True)
                conda_sh=prefix/'etc/profile.d/conda.sh'
                conda_sh.write_text('''conda() {
    printf 'conda %s\\n' "$*" >> "$CRC_TEST_LOG"
    case "$1" in
        info) printf '%s\\n' "$CRC_TEST_PREFIX" ;;
        env)
            if [[ "$2" == list ]]; then
                if [[ "$CRC_TEST_EXISTS" == 1 ]]; then echo 'tda /shared/envs/tda'; fi
            fi
            ;;
        activate) export PATH="$CRC_TEST_BIN:$PATH" ;;
        *) return 2 ;;
    esac
}
''')
                bash_env=root/'bootstrap.sh'
                bash_env.write_text('''module() {
    printf 'module %s\\n' "$*" >> "$CRC_TEST_LOG"
    source "$CRC_TEST_PREFIX/etc/profile.d/conda.sh"
}
''')
                env={key:value for key,value in os.environ.items()
                     if not key.startswith(('CONDA','BASH_FUNC_')) and key!='BASH_ENV'}
                env.update(PATH=str(bin_dir)+':/usr/bin:/bin',HOME=str(root/'home'),BASH_ENV=str(bash_env),
                           CRC_TEST_LOG=str(root/'commands.log'),CRC_TEST_PREFIX=str(prefix),
                           CRC_TEST_BIN=str(bin_dir),CRC_TEST_EXISTS='1' if existing else '0')
                result=subprocess.run(['/bin/bash','jobs/setup_crc.sh'],cwd=repo,env=env,capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                config=repo/'jobs/crc_conda.local.sh'
                self.assertTrue(config.exists())
                self.assertEqual(config.stat().st_mode&0o777,0o600)
                commands=(root/'commands.log').read_text()
                self.assertIn('module load conda',commands)
                expected='conda env update --name tda --file environment-crc.yml' if existing else 'conda env create --file environment-crc.yml'
                self.assertIn(expected,commands)
                self.assertNotIn('--prune',commands)
                self.assertIn('conda activate tda',commands)
                python_calls=[json.loads(line) for line in commands.splitlines() if line.startswith('[')]
                self.assertIn(['-B','-m','unittest','discover','-s','tests','-v'],python_calls)
                # A new batch shell has no conda function, module or CONDA_SH.
                del env['BASH_ENV']
                activate=subprocess.run(['/bin/bash','-c',
                    'set -euo pipefail; source jobs/crc_conda.sh; initialize_crc_conda; conda activate tda; test "$PYTHONNOUSERSITE" = 1'],
                    cwd=repo,env=env,capture_output=True,text=True)
                self.assertEqual(activate.returncode,0,activate.stderr)


if __name__=='__main__':unittest.main()
