/**
 * Distributed under the terms of the BSD 3-Clause License.
 *
 * The full license is in the file LICENSE, distributed with this software.
 *
 * Author: Jun Zhu <jun.zhu@xfel.eu>
 * Copyright (C) European X-Ray Free-Electron Laser Facility GmbH.
 * All rights reserved.
 */
#define FORCE_IMPORT_ARRAY
#include "xtensor-python/pytensor.hpp"

namespace foam
{

template<typename T, xt::layout_type L>
struct IsImage<xt::pytensor<T, 2, L>> : std::true_type {};

template<typename T, xt::layout_type L>
struct IsImageArray<xt::pytensor<T, 3, L>> : std::true_type {};

template<typename T, xt::layout_type L>
struct IsModulesArray<xt::pytensor<T, 4, L>> : std::true_type {};

template<typename T, xt::layout_type L>
struct IsModulesVector<std::vector<xt::pytensor<T, 3, L>>> : std::true_type {};

} // foam
