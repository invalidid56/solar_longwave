# invalidid56@snu.ac.kr 작물생태정보연구실 강준서
# define model and fit
# save model in result_dir/model/$index, save log in result_dir/log/$index, save plot in result_dir/plot
# train.py temp_dir result_dir params
import os.path
import shutil
import sys
import math
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import r2_score, mean_squared_error
from keras.models import load_model
from datagen import minmax_norm, z_norm, accumulate


def main(result_dir, temp_dir, target, params='params.txt'):
    #
    # Estimate, Plot Model
    #
    para = []
    for i, line in enumerate(open(params, 'r')):
        if not i == 2:
            para.append(int(line.strip().split('=')[1]))
        else:
            para.append(float(line.strip().split('=')[1]))

    FOLD, EPOCH, LEARNING_RATE, BATCH = para

    #
    # For Each Style: Day and Night
    #
    data_styles = ['HEADING', 'AFTER']
    for data_style in data_styles:
        test_set = pd.read_csv(os.path.join(result_dir, target, data_style, 'data', 'test.csv'))

        if target == 'LEAF':
            test_y = test_set.LEAF
            test_x = test_set.drop(['LEAF', 'RECO_DT', 'GPP_DT', 'YEAR_SITE'], axis=1)

        elif target == 'GPP':
            test_y = test_set.GPP_DT
            test_x = test_set.drop(['GPP_DT', 'RECO_DT', 'YEAR_SITE'], axis=1)

        elif target == 'RECO':
            test_y = test_set.RECO_DT
            test_x = test_set.drop(['RECO_DT', 'YEAR_SITE'], axis=1)

        # Loss in a Bar

        test_losses = []
        r2_socres = []
        nrmse_scores = []

        for i in range(FOLD):
            Model = load_model(os.path.join(result_dir, target, data_style, 'model', str(i)))
            eval_result = Model.evaluate(test_x, test_y)

            x_values = test_x.values.tolist()
            ys_expect = Model.predict(x_values).tolist()
            ys_expect = pd.Series([y[0] for y in ys_expect])

            r2_socres.append(r2_score(test_y, ys_expect))
            nrmse_scores.append(mean_squared_error(test_y, ys_expect)/(max(test_y)-min(test_y))*100)
            test_losses.append(math.sqrt(eval_result[1]))   # MAE

        plt.bar(list(range(FOLD)), nrmse_scores)
        plt.xticks(list(range(FOLD)), list(range(1, FOLD+1)))

        plt.savefig(os.path.join(result_dir, target, data_style, 'plot', 'nrmse_per_model.png'))
        plt.clf()

        # CSV: Site, Predict, Real, DOY 1 to 1 plot for a best model
        best_model = test_losses.index(min(test_losses))

        model = load_model(os.path.join(result_dir, target, data_style, 'model', str(best_model)))

        test_x = test_x.values.tolist()
        ys_expect = model.predict(test_x).tolist()
        ys_expect = pd.Series([y[0] for y in ys_expect])

        result_df = pd.concat([test_set['YEAR_SITE'], ys_expect, test_y], axis=1)
        result_df.columns = ['YEAR_SITE', 'EXPECT', 'REAL']
        result_df['LOSS'] = result_df['REAL']-result_df['EXPECT']

        plt.plot(test_y, ys_expect, 'bo')
        plt.plot(test_y, test_y, 'r')

        plt.savefig(os.path.join(result_dir, target, data_style, 'plot', 'one_to_one.png'))
        plt.clf()

        result_df['DOY'] = test_set['DAY_PER_YEAR']

        result_df.to_csv(os.path.join(result_dir, target, data_style, 'plot', 'result.csv'), index=False)

        # Print Estimate Report as a File

        with open(os.path.join(result_dir, target, data_style, 'estimate_report.txt'), 'w') as report:
            for i, tl in enumerate(test_losses):
                report.write(
                    'Model No. {0} in {1} Style-\n Test Loss: {2}\nR2 Score: {3}\nNRMSE Score: {4}%'.format(
                        i, data_style, tl, r2_socres[i], nrmse_scores[i]
                    )
                )
        #
        # LEAF-GPP-RECO
        # origin: RECO LEAF GPP
        if target == 'LEAF':
            if os.path.exists(os.path.join(temp_dir, 'GPP')):
                shutil.rmtree(os.path.join(temp_dir, 'GPP'))
            os.mkdir(os.path.join(temp_dir, 'GPP'))

            for data_style in ('HEADING', 'AFTER'):
                temp_data = pd.read_csv(os.path.join(temp_dir, target, 'temp_{0}.csv'.format(data_style)))
                temp_data = temp_data.drop(['LEAF'], axis=1)
                temp_x = temp_data.drop(['GPP_DT', 'RECO_DT',
                                         'YEAR_SITE'], axis=1).values.tolist()
                ys_expect = model.predict(temp_x).tolist()
                ys_expect = pd.Series([y[0] for y in ys_expect], name='LEAF')

                result_df = pd.concat([temp_data, ys_expect], axis=1)
                result_df.to_csv(os.path.join(temp_dir, 'GPP', 'temp_{0}.csv'.format(data_style)), index=False)

        elif target== 'GPP':
            if os.path.exists(os.path.join(temp_dir, 'RECO')):
                shutil.rmtree(os.path.join(temp_dir, 'RECO'))
            os.mkdir(os.path.join(temp_dir, 'RECO'))

            for data_style in ('HEADING', 'AFTER'):
                temp_data = pd.read_csv(os.path.join(temp_dir, target, 'temp_{0}.csv'.format(data_style)))
                temp_data = temp_data.drop(['GPP_DT'], axis=1)
                temp_x = temp_data.drop(['RECO_DT', 'YEAR_SITE'], axis=1).values.tolist()
                ys_expect = model.predict(temp_x).tolist()
                ys_expect = pd.Series([y[0] for y in ys_expect], name='GPP_DT')

                ys_acc = minmax_norm(z_norm(accumulate(
                    sr=ys_expect,
                    year_site=temp_data['YEAR_SITE'],
                    day_per_year=temp_data['DAY_PER_YEAR'],
                    threshold=0,
                    cold_day=14
                )))
                ys_acc.name = 'ACC_GPP'

                result_df = pd.concat([temp_data, ys_expect, ys_acc], axis=1)
                result_df.to_csv(os.path.join(temp_dir, 'RECO', 'temp_{0}.csv'.format(data_style)), index=False)

    return True


if __name__ == '__main__':
    main(result_dir=sys.argv[1],
         temp_dir=sys.argv[2],
         target=sys.argv[3])
