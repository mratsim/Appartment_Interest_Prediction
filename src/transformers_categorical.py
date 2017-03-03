from sklearn.preprocessing import LabelEncoder
import pandas as pd
import string
# import pandas as pd

# WARNING - Deprecated - LabelEncoder is directly usable at the feat selection stage
# Furthermore LightGBM core dumped on pandas 'category'
# LightGBM removed categoricals support on commit 10212b5 around Feb 18

# Besides, according to Sklearn core devs, LabelEncoder should only be used for label (y).
# It does not provide the same interface as others as it does not take X, y parameter, only y
# As such it cannot be use in a Pipeline.


# DEPRECATED Apply Label encoder
def _encode_categoricals(train,test, sColumn):
    le = LabelEncoder() 
    le.fit(list(train[sColumn].values) + list(test[sColumn].values))
    
    def _trans(df, sColumn, le):
        encoded = le.transform(df[sColumn])
        df['encoded_' + sColumn] = encoded
        # df['encoded_' + sColumn] = df['encoded_' + sColumn].astype('category')
        return df
    return _trans(train, sColumn, le),_trans(test, sColumn, le)

def tr_encoded_manager(train, test, y, cache_file):
    trn, tst = _encode_categoricals(train,test,"manager_id")
    return trn, tst, y, cache_file
def tr_encoded_building(train, test, y, cache_file):
    trn, tst = _encode_categoricals(train,test,"building_id")
    return trn, tst, y, cache_file
def tr_encoded_disp_addr(train, test, y, cache_file):
    trn, tst = _encode_categoricals(train,test,"display_address")
    return trn, tst, y, cache_file
def tr_encoded_street_addr(train, test, y, cache_file):
    trn, tst = _encode_categoricals(train,test,"street_address")
    return trn, tst, y, cache_file

def tr_filtered_display_addr(train, test, y, cache_file):
    address_map = {
    'w': 'west',
    'st.': 'street',
    'ave': 'avenue',
    'st': 'street',
    'e': 'east',
    'n': 'north',
    's': 'south'
    }
    remove_punct_map = dict.fromkeys(map(ord, string.punctuation))
    def _address_map_func(s):
        s = s.split(' ')
        out = []
        for x in s:
            if x in address_map:
                out.append(address_map[x])
            else:
                out.append(x)
        return ' '.join(out)
    def _trans(df):
        df = df.assign(
            filtered_address = df['display_address']
                                    .apply(str.lower)
                                    .apply(lambda x: x.translate(remove_punct_map))
                                    .apply(lambda x: _address_map_func(x))
        )
        new_cols = ['street', 'avenue', 'east', 'west', 'north', 'south']

        for col in new_cols:
            df[col] = df['filtered_address'].apply(lambda x: 1 if col in x else 0)

        df['other_address'] = df[new_cols].apply(lambda x: 1 if x.sum() == 0 else 0, axis=1)
        return df
    
    return _trans(train), _trans(test), y, cache_file

#############
# Manager skill
def tr_managerskill(train, test, y, cache_file):
    # Beware of not leaking "mean" or frequency from train to test.
    
    df_mngr = (pd.concat([train['manager_id'], 
                           pd.get_dummies(train['interest_level'])], axis = 1)
                                        .groupby('manager_id')
                                        .mean()
                                        .rename(columns = lambda x: 'mngr_percent_' + x)
                                           )
    df_mngr['mngr_count']=train.groupby('manager_id').size()
    df_mngr['mngr_skill'] = df_mngr['mngr_percent_high']*2 + df_mngr['mngr_percent_medium']
    # get ixes for unranked managers...
    unrkd_mngrs_ixes = df_mngr['mngr_count']<20
    # ... and ranked ones
    rkd_mngrs_ixes = ~unrkd_mngrs_ixes

    # compute mean values from ranked managers and assign them to unranked ones
    mean_val = df_mngr.loc[rkd_mngrs_ixes,
                           ['mngr_percent_high',
                            'mngr_percent_low',
                            'mngr_percent_medium',
                            'mngr_skill']].mean()
    df_mngr.loc[unrkd_mngrs_ixes, ['mngr_percent_high',
                                    'mngr_percent_low',
                                    'mngr_percent_medium',
                                    'mngr_skill']] = mean_val.values

    trn = train.merge(df_mngr.reset_index(),how='left', left_on='manager_id', right_on='manager_id')
    tst = test.merge(df_mngr.reset_index(),how='left', left_on='manager_id', right_on='manager_id')
        
    new_mngr_ixes = tst['mngr_percent_high'].isnull()
    tst.loc[new_mngr_ixes,['mngr_percent_high',
                                    'mngr_percent_low',
                                    'mngr_percent_medium',
                                    'mngr_skill']]  = mean_val.values

    return trn, tst, y, cache_file


#############
# Bins managers and building
def tr_bin_buildings_mngr(train, test, y, cache_file):
    def _trans(df):
        return df.assign(
            #duplicates = drop avoids error whena single value would need to appear in 2 different bins
            #It needs pandas version>=20.0
            #It's probably better to cut by value if distrbution between training and tests are different
            
            Bin_Buildings = pd.qcut(df['building_id'].value_counts(), 30, labels=False,duplicates='drop'),
            Bin_Managers = pd.qcut(df['manager_id'].value_counts(), 30, labels=False, duplicates='drop')
            )
    # Since we don't use y, there shouldn't be leakage if we use the total count train + test.
    return _trans(train), _trans(test), y, cache_file
    