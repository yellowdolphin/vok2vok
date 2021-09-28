import os
from glob import glob
import argparse
import xml.etree.ElementTree as ET
import sqlite3

import pandas as pd

vok2_fields = 'lektion spreins sprzwei synonym bemerkung'.split()

vok5_fields = ['LessonsID', 'Language1', 'Language2', 'Synonyms1',
               'Synonyms2', 'Pronunciation1', 'Pronunciation2', 'Comment',
               'ImageFilename', 'PronunciationFilename1', 'PronunciationFilename2',
               'Box12', 'Box21', 'LastLearned12', 'LastLearned21', 'Counter12',
               'Counter21']

map_fields = {
    'spreins'  : 'Language1',
    'sprzwei'  : 'Language2',
    'synonym'  : 'Synonyms1',    # assume vok2 synonyms refer to first language
    'bemerkung': 'Comment',
}

empty_str_fields = ['Pronunciation1', 'Pronunciation2',
                    'ImageFilename', 'PronunciationFilename1', 'PronunciationFilename2',
                    'LastLearned12', 'LastLearned21']

vocab_name = 'vokabelsatz'

def vok2_to_csv(files, overwrite=False):
    "Extract vocabulary from vok2 file(s) and save to csv file(s)"
    n_written = 0
    for file in files:
        if not os.path.exists(file):
            print(f"{file} not found, skipping.")
            continue
        csv_file = file.replace('.vok2', '.csv')
        if os.path.exists(csv_file) and not overwrite:
            print(f"{csv_file} already exists, skipping (use -f to override).")
            continue
        root = ET.parse(file).getroot()
        vocab = []
        for s in root.iterfind(vocab_name):
            vocab.append({field: s.find(field).text or '' for field in vok2_fields})
        pd.DataFrame(vocab).to_csv(csv_file, sep=';', index=False, header=False)
        n_written += 1
    print(f"Converted {n_written} / {len(files)} vok2 files to csv.")

def fix_synonyms(row):
    """Move synonyms from LanguageX to SynonymsX
    
    Synonym handling changed in teachmaster 5:
    - Synonyms accepted individually as correct answer are only allowed in `SynonymsX` fields
    - The entire value of the `LanguageX` field must match the answer
    - `LanguageX` field must not be empty, otherwise "" counts as correct answer
    """
    lang_fields = ['Language1', 'Language2']
    syno_fields = ['Synonyms1', 'Synonyms2']
    for lang, syno in zip(lang_fields, syno_fields):
        if syno not in row: row[syno] = ''
        if ';' in row[lang]:
            synonyms = [w.strip() for w in row[lang].split(';')] + [w.strip() for w in row[syno].split(';') if w != '']
            row[lang] = synonyms.pop(0)       # keep first entry in LanguageX field
            row[syno] = '; '.join(synonyms)
    return row

def get_kk(vok2_file):
    "Return box number containing each word, or 5 if kk-file is missing."
    kk_file = vok2_file.replace('.vok2', '.kk')
    if not os.path.exists(kk_file): return 5
    with open(kk_file, 'r') as f:
        kks = f.read().split()
    return [int(kk) for kk in kks]


if __name__ == "__main__":

    # Command line arguments
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("files", nargs='*', default=glob("*.vok2"), help='vok2 files to be converted')
    parser.add_argument("--csv", action='store_true', help='Write csv files instead of vok5')
    parser.add_argument("-f", "--overwrite", action='store_true', help='Overwrite existing output files')
    args = parser.parse_args()

    overwrite = args.overwrite
    write_csv = args.csv
    files = args.files
    if not files:
        parser.print_help()
        exit()

    # Convert to csv
    if write_csv:
        vok2_to_csv(files, overwrite=overwrite)
        exit()

    # Convert to vok5 (sqlite3)
    print(f"Processing {len(files)} vok2 (and kk) files...")
    n_written = 0
    for file in files:
        if not os.path.exists(file):
            print(f"{file} not found, skipping.")
        vok5_file = file.replace('.vok2', '.vok5')
        if os.path.exists(vok5_file) and not overwrite:
            print(f"{vok5_file} already exists, skipping (use -f to override).")
            continue
        elif os.path.exists(vok5_file):
            os.remove(vok5_file)
        root = ET.parse(file).getroot()
        
        vocab = []
        for s in root.iterfind(vocab_name):
            vocab.append({field: s.find(field).text or '' for field in vok2_fields})
        vocab = pd.DataFrame(vocab).rename(columns=map_fields).apply(fix_synonyms, axis=1)
        vocab['VocabularyID'] = vocab.index.values + 1
        vocab.set_index('VocabularyID', drop=True, inplace=True)
        vocab['lektion'] = vocab.lektion.astype("category")
        vocab['LessonsID'] = vocab.lektion.cat.codes.astype('int64') + 1
        kk = get_kk(file)
        vocab['Box12'] = kk
        vocab['Box21'] = kk
        vocab['Counter12'] = 0
        vocab['Counter21'] = 0
        for f in empty_str_fields:
            vocab[f] = ''
            
        lessons = pd.DataFrame({
            'LessonsID': range(1, len(vocab.lektion.cat.categories) + 1), 
            'Name': vocab.lektion.cat.categories
        }).set_index('LessonsID', drop=True)
        
        settings = pd.DataFrame({
            'SettingsID': [1, 2, 3, 4, 5],
            'Name': ['Title', 'DescriptionLanguage1', 'DescriptionLanguage2', 'LastDirection', 'Separator'],
            'Value': [root.find('header').find('titel').text or '',
                      root.find('header').find('spreins').text or '',
                      root.find('header').find('sprzwei').text or '',
                      1,
                      ';']
        }).set_index('SettingsID', drop=True)
        
        statistics = pd.DataFrame(
            columns=[
                'StatisticsID', 'LessonsID', 'Datetime', 'Duration', 'NumberTotal',
                'NumberCorrect', 'NumberWrong', 'NumberAccepted', 'Method', 'Type',
                'QueryType', 'Direction'],
            dtype='int64'
        ).set_index('StatisticsID', drop=True)
        statistics['Datetime'] = statistics.Datetime.astype(object)
            
        id_type = 'INTEGER PRIMARY KEY AUTOINCREMENT'
        with sqlite3.connect(vok5_file) as con:
            lessons.to_sql('Lessons', con=con, dtype={'LessonsID': id_type})
            settings.to_sql('Settings', con=con, dtype={'SettingsID': id_type})
            vocab[vok5_fields].to_sql('Vocabulary', con=con, dtype={'VocabularyID': id_type})
            statistics.to_sql('Statistics', con=con, dtype={'StatisticsID': id_type})
        n_written += 1

    print(f"Converted {n_written} / {len(files)} vok2 files to vok5.")
