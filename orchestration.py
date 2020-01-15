# Orchestration 
# Author: Jintao Long <jintaolong@brookes.ac.uk>

__doc__ = """
	A integrated orchestration of NLK text preprocessing
	classifier model training and testing and evaluation
"""

import argparse
import json
import datetime
import os
import logging

from os import listdir

from preprocessing import DocxPreprocessing, RtfPreprocessing
from learning import ModelClassSelector
from db.db_connector import DBConnector
from db.config import PPC_TABLE
from event_logger import logger

PREPROCESS_CLS_MAP = {
	'rtf': RtfPreprocessing,
	'docx': DocxPreprocessing
}
TRAINING_INGREDIENT_PATH = 'training_ingredients/'
MIDDLE_INGREDIENT_PATH = 'middleware_ingredients/'
CONTRACT_PATH = 'contracts/'

def merge_datasets(path_to_merge, filename=None) -> str:
	# get list of json txt files
	training_ingredient_path = os.path.join(
		os.getcwd(),
		path_to_merge
	)
	files = listdir(training_ingredient_path)
	aggregate = []
	for file in files:
		if file.startswith('Cont'):
			# only process those names starting with Cont_
			filepath = os.path.join(
				training_ingredient_path,
				file
			)
			json_txt = open(filepath).read()
			file_json = json.loads(json_txt)
			aggregate += file_json
	if not filename:
		timestamp = datetime.datetime.strftime(
				datetime.datetime.now(), "%Y%m%d%H%M%S")
		filename = timestamp+'.txt'
	output_filepath = os.path.join(
		os.getcwd(), 
		path_to_merge, 
		filename
	)
	f = open(output_filepath, 'w')
	f.write(json.dumps(aggregate))
	f.close()
	return filename

def create_learning_entry(
		start_time, 
		end_time, 
		embedding_method: str,
		tag_obtaining_method: str,
		remove_stop_words: str,
		do_stemming: str,
		strigent_topic: str,
		sample_file_path: str,
		exclude_file_names: list
	) -> int:
	"""
	Create a learning record/entry in DB for this preprocessing action
	trigged after every preprocessing and before a training take place
	
	:Return: an 'id' will be returned which can then be passed 
	into the ML tranining process
	"""
	conn = DBConnector()
	exclude_filename_string = ''
	if len(exclude_file_names) > 0:
		exclude_filename_string = ','.join(exclude_file_names)

	return conn.insert(
		PPC_TABLE,
		stop_word_removed=remove_stop_words,
		stemming=do_stemming,
		preprocessing_start=start_time,
		preprocessing_end=end_time,
		sample_file_path=sample_file_path,
		embedding_method=embedding_method,
		strigent_topic=strigent_topic,
		exclude_contracts=exclude_filename_string
	)

def main(
		action: str,
		file_path: str,
		exclude_file_names: list,
		input_file_format: str,
		embedding_method: str, 
		tag_obtaining_method: str, 
		remove_stop_words: bool, 
		do_stemming: bool,
		strigent_topic: bool,
		training_id: int,
		topic: str,
		model: str,
		cv_fold_num: int
	):
	"""
	Main initializer of complete NLP study
	"""
	if action == 'preprocess':
		contracts_path = os.path.join(
			os.getcwd(),
			CONTRACT_PATH
		)
		file_paths = listdir(contracts_path)
		if file_path:
			file_paths = [
				os.path.join(
					os.getcwd(),
					file_path
				)
			]
			if file_path.endswith('.rtf'):
				input_file_format = 'rtf'
			elif file_path.endswith('.docx'):
				input_file_format = 'docx'
			else:
				raise Exception("""
					Input contract file type not supported.
					Only .rtf and .docx are supported.
				""")
		else:
			file_paths = [os.path.join(contracts_path, p) for p in file_paths]

		preprocess_cls = PREPROCESS_CLS_MAP[input_file_format]
		preprocessing_start = datetime.datetime.strftime(
			datetime.datetime.now(), "%Y-%m-%d %H:%M:%S")

		#TODO: Empty training ingredients first!
		for fp in file_paths:
			skip_file = False
			for efn in exclude_file_names:
				# skip selected contracts that passed through
				if efn in fp:
					skip_file = True
					break
			if skip_file:
				continue
			if fp.endswith(input_file_format):
				# only process specified file formats
				individual_file_preprocess_engine = preprocess_cls(
					fp, 
					embedding_method,
					tag_obtaining_method,
					remove_stop_words,
					do_stemming,
					strigent_topic
				)
				try:
					individual_file_preprocess_engine.bag_of_word_dict_transformer()
				except Exception as e: 
					logger.error(fp+"\n "+str(e))

		sample_file_path = merge_datasets(TRAINING_INGREDIENT_PATH)
		# merge datasets in middleware for referencing
		_ = merge_datasets(
			MIDDLE_INGREDIENT_PATH, filename=sample_file_path)

		preprocessing_end = datetime.datetime.strftime(
			datetime.datetime.now(), "%Y-%m-%d %H:%M:%S")

		new_row_id = create_learning_entry(
			preprocessing_start,
			preprocessing_end,
			embedding_method,
			tag_obtaining_method,
			remove_stop_words,
			do_stemming,
			strigent_topic,
			sample_file_path,
			exclude_file_names
		)

		print(
			"""New result entry ID is: \n %s \n 
			Please use it in training""" % (new_row_id)
		)

	elif action == 'train-test':
		train_classifier = ModelClassSelector(
			).convert_string_to_classifier(model)
		train_classifier(
			training_id,
			topic,
			cv_fold_num
		)
	else:
		raise Exception("""
			Wrong action: available options 'preprocess'/'trian-test'
		""")



if __name__ == '__main__':

	"""
	file_path, embedding_method, tag_obtaining_method,
		remove_stop_words: bool, do_stemming: bool
	"""
	parser = argparse.ArgumentParser(description="""
		Preprocess, train and test NLP classifier model
	""")
	parser.add_argument(
		"--action",
		choices=['preprocess', 'train-test'], 
		help="What action to take", 
		dest="action",
		required=True
	)
	parser.add_argument(
		"--file-path",
		help="A specific file to preprocess", 
		dest="file_path"
	)
	parser.add_argument(
		"--input-file-format", 
		help="Contract file path to be processed", 
		dest="input_file_format",
		default="rtf"
	)
	parser.add_argument(
		"--exclude", 
		nargs='*',
		help="To be excluded file names", 
		dest="exclude_file_names",
		default=[]
	)
	parser.add_argument(
		"--embedding-method", 
		help="How to quantify words", 
		dest="embedding_method",
		default="count_occurence"
	)
	parser.add_argument(
		"--tag-obtaining-method", 
		help="How to obtain tags", 
		dest="tag_obtaining_method",
		default="heading_as_label"
	)
	parser.add_argument(
		"--remove-stop-words", 
		help="Removing stop words or not", 
		dest="remove_stop_words",
		default=True,
		type=bool
	)
	parser.add_argument(
		"--do-stemming", 
		help="Do stemming or not", 
		dest="do_stemming",
		default=True,
		type=bool
	)
	parser.add_argument(
		"--strigent-topic", 
		help="Striggent topic search", 
		dest="strigent_topic",
		default=True,
		type=bool
	)
	parser.add_argument(
		"--training-id", 
		help="ID returned from preprocessing", 
		dest="training_id",
		type=int
	)
	parser.add_argument(
		"--topic", 
		help="Train to classify a specific topic", 
		dest="topic",
		type=str,
		default=None
	)
	parser.add_argument(
		"--model", 
		help="""Model to train classifier, available options including \n
			'naive_bayes': 'SimpleNaiveBayesClassifying',
			'multinomial_nb': 'MultinomialNBClassifying',
			'gaussian_nb': 'GuassianNBClassifying',
			'bernoulli_nb': 'BernoulliNBClassifying',
			'logistic_regression': 'LogisticClassifying',
			'sgdc': 'SGDCClassifying',
			'svc': 'SVCClassifying',
			'linear_svc': 'LinearSVCClassifying',
			'nu_svc': 'NuSVCClassifying',
			'gaussian_mixure': 'GaussianMixureClassifying'
		""", 
		dest="model",
		default="naive_bayes"
	)
	parser.add_argument(
		"--cv-fold-number", 
		help="Cross validation fold number", 
		dest="cv_fold_num",
		default=5
	)
	args = parser.parse_args()

	if args.action == 'preprocess':
		print("""
			The action is chosen to preprocess contracts \n
		""")
		if args.file_path is None:
			print("""
				No single file was passed \n
				Batch processing all files under contract folder... \n
			""")
	else:
		print("""
			The action is chosen to train and test classifying models \n
		""")

	if args.action == 'train-test':
		if args.training_id is None:
			raise Exception("""
				No training ID passed for learning \n
			""")
	main(
		args.action,
		args.file_path,
		args.exclude_file_names,
		args.input_file_format,
		args.embedding_method,
		args.tag_obtaining_method,
		args.remove_stop_words,
		args.do_stemming,
		args.strigent_topic,
		args.training_id,
		args.topic,
		args.model,
		args.cv_fold_num
	)