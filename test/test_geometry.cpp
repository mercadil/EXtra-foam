/**
 * Distributed under the terms of the BSD 3-Clause License.
 *
 * The full license is in the file LICENSE, distributed with this software.
 *
 * Author: Jun Zhu <jun.zhu@xfel.eu>
 * Copyright (C) European X-Ray Free-Electron Laser Facility GmbH.
 * All rights reserved.
 */
#include "gtest/gtest.h"
#include "gmock/gmock.h"

#include <memory>
#include <type_traits>

#include "xtensor/xio.hpp"

#include "f_geometry.hpp"

namespace foam
{
namespace test
{

using ::testing::ElementsAre;
using ::testing::ElementsAreArray;
using ::testing::NanSensitiveFloatEq;
using ::testing::FloatEq;


TEST(TestGeometry, TestWrongColumnNumber)
{
  EXPECT_THROW(DetectorGeometry<JungFrau>(1, 3), std::invalid_argument);
  EXPECT_THROW(DetectorGeometry<EPix100>(2, 4), std::invalid_argument);

}

size_t N_ROWS = 3;
size_t N_COLS = 2;

template<typename T>
class Geometry : public ::testing::Test
{
public:
  using GeometryType = T;

protected:
  Geometry() : geom_(std::make_unique<T>(N_ROWS, N_COLS)) {}

  ~Geometry() = default;

  std::unique_ptr<T> geom_;

  float nan = std::numeric_limits<float>::quiet_NaN();
  typename T::ShapeType shape = geom_->assembledShape();
  typename T::CenterType center = geom_->assembledCenter();

  size_t np_ = 2; // number of pulses
  size_t nm_ = geom_->nModules();
  size_t mw_ = geom_->moduleShape()[1];
  size_t mh_ = geom_->moduleShape()[0];
  size_t aw_ = geom_->asicShape()[1];
  size_t ah_ = geom_->asicShape()[0];
};


using GeometryTypes = ::testing::Types<DetectorGeometry<JungFrau>, DetectorGeometry<EPix100>>;
TYPED_TEST_CASE(Geometry, GeometryTypes);

TYPED_TEST(Geometry, testAssembledShapeAndCenter)
{
  EXPECT_THAT(this->shape, ElementsAre(N_ROWS * this->mh_, N_COLS * this->mw_));
//  EXPECT_THAT(this->center, ElementsAre(this->mw_, 1.5 * this->mh_));
}

TYPED_TEST(Geometry, testAssemblingShapeCheck)
{
  // src and dst have different memory cells
  xt::xtensor<float, 4> src1{xt::ones<float>({this->np_ - 1, this->nm_, this->mh_, this->mw_})};
  xt::xtensor<float, 3> dst1{xt::empty<float>({this->np_, this->shape[0], this->shape[1]})};
  EXPECT_THROW(this->geom_->positionAllModules(src1, dst1), std::invalid_argument);

  // src has incorrect shape
  xt::xtensor<float, 3> dst2 {xt::empty<float>({this->np_, this->shape[0], this->shape[1]})};
  xt::xtensor<float, 4> src2_1{xt::ones<float>({this->np_, this->nm_ - 1, this->mh_, this->mw_})};
  EXPECT_THROW(this->geom_->positionAllModules(src2_1, dst2), std::invalid_argument);
  xt::xtensor<float, 4> src2_2 { xt::ones<float>({this->np_, this->nm_, this->mh_ - 1, this->mw_}) };
  EXPECT_THROW(this->geom_->positionAllModules(src2_2, dst2), std::invalid_argument);
  xt::xtensor<float, 4> src2_3 { xt::ones<float>({this->np_, this->nm_, this->mh_, this->mw_ - 1}) };
  EXPECT_THROW(this->geom_->positionAllModules(src2_3, dst2), std::invalid_argument);

  // dst has incorrect shape
  xt::xtensor<float, 4> src3 { xt::ones<float>({this->np_, this->nm_, this->mh_, this->mw_}) };
  xt::xtensor<float, 3> dst3_1 {xt::empty<float>({this->np_, this->shape[0] + 1, this->shape[1]}) };
  EXPECT_THROW(this->geom_->positionAllModules(src3, dst3_1), std::invalid_argument);
  xt::xtensor<float, 3> dst3_2 {xt::empty<float>({this->np_, this->shape[0], this->shape[1] + 1}) };
  EXPECT_THROW(this->geom_->positionAllModules(src3, dst3_1), std::invalid_argument);
}

TYPED_TEST(Geometry, testPositionAllModulesSingle)
{
  xt::xtensor<float, 3> src { xt::ones<float>({this->nm_, this->mh_, this->mw_}) };
  xt::xtensor<float, 2> dst { xt::empty<float>({this->shape[0], this->shape[1]}) };

  this->geom_->positionAllModules(src, dst); // test no throw
  EXPECT_THAT(dst, ::testing::Each(1.f));
}

TYPED_TEST(Geometry, testPositionAllModulesSingleVector)
{
  std::vector<xt::xtensor<float, 2>> src;
  for (size_t i = 0; i < this->nm_; ++i) src.emplace_back(xt::ones<float>({this->mh_, this->mw_}));
  xt::xtensor<float, 2> dst { xt::empty<float>({this->shape[0], this->shape[1]}) };

  this->geom_->positionAllModules(src, dst); // test no throw
  EXPECT_THAT(dst, ::testing::Each(1.f));
}

TYPED_TEST(Geometry, testPositionAllModulesArray)
{
  xt::xtensor<float, 4> src { xt::ones<float>({this->np_, this->nm_, this->mh_, this->mw_}) };
  xt::xtensor<float, 3> dst { xt::empty<float>({this->np_, this->shape[0], this->shape[1]}) };

  this->geom_->positionAllModules(src, dst); // test no throw
  EXPECT_THAT(dst, ::testing::Each(1.f));
}

TYPED_TEST(Geometry, testPositionAllModulesVector)
{
  std::vector<xt::xtensor<float, 3>> src;
  for (size_t i = 0; i < this->nm_; ++i) src.emplace_back(xt::ones<float>({this->np_, this->mh_, this->mw_}));
  xt::xtensor<float, 3> dst { xt::empty<float>({this->np_, this->shape[0], this->shape[1]}) };

  this->geom_->positionAllModules(src, dst); // test no throw
  EXPECT_THAT(dst, ::testing::Each(1.f));
}

TYPED_TEST(Geometry, testIgnoreTileEdge)
{
  using GeometryType = typename TestFixture::GeometryType;

  xt::xtensor<float, 3> dst { xt::empty<float>({this->np_, this->shape[0], this->shape[1]}) };
  dst.fill(this->nan);

  xt::xtensor<float, 4> src { xt::ones<float>({this->np_, this->nm_, this->mh_, this->mw_}) };
  this->geom_->positionAllModules(src, dst, true);

  EXPECT_THAT(xt::view(dst, 0, 0, xt::all()), ::testing::Each(NanSensitiveFloatEq(this->nan)));

  if (std::is_same<GeometryType, DetectorGeometry<EPix100>>::value)
  {
    for (size_t bottom=0, top = this->mh_ - 1; bottom < this->shape[0]; top += this->mh_, bottom += this->mh_)
    {
      EXPECT_THAT(xt::view(dst, xt::all(), bottom, xt::all()), ::testing::Each(NanSensitiveFloatEq(this->nan)));
      EXPECT_THAT(xt::view(dst, xt::all(), top, xt::all()), ::testing::Each(NanSensitiveFloatEq(this->nan)));
    }
  } else
  {
    for (size_t bottom=0, top = this->ah_ - 1; bottom < this->shape[0]; top += this->ah_, bottom += this->ah_)
    {
      EXPECT_THAT(xt::view(dst, xt::all(), bottom, xt::all()), ::testing::Each(NanSensitiveFloatEq(this->nan)));
      EXPECT_THAT(xt::view(dst, xt::all(), top, xt::all()), ::testing::Each(NanSensitiveFloatEq(this->nan)));
    }
    for (size_t left = 0, right = this->aw_ - 1; right < this->shape[1]; left += this->aw_, right += this->aw_)
    {
      EXPECT_THAT(xt::view(dst, xt::all(), xt::all(), left), ::testing::Each(NanSensitiveFloatEq(this->nan)));
      EXPECT_THAT(xt::view(dst, xt::all(), xt::all(), right), ::testing::Each(NanSensitiveFloatEq(this->nan)));
    }
  }
}

TYPED_TEST(Geometry, testMaskModule)
{
  using GeometryType = typename TestFixture::GeometryType;

  xt::xtensor<float, 2> src_w { xt::ones<float>({3, 4}) };
  EXPECT_THROW(GeometryType::maskModule(src_w), std::invalid_argument);

  xt::xtensor<float, 2> src { xt::ones<float>({this->mh_, this->mw_}) };
  GeometryType::maskModule(src);

  if (std::is_same<GeometryType, DetectorGeometry<EPix100>>::value)
  {
    EXPECT_THAT(xt::view(src, 0, xt::all()), ::testing::Each(NanSensitiveFloatEq(this->nan)));
    EXPECT_THAT(xt::view(src, this->mh_ - 1, xt::all()), ::testing::Each(NanSensitiveFloatEq(this->nan)));
  } else
  {
    for (size_t bottom=0, top = this->ah_ - 1; bottom < this->mh_; top += this->ah_, bottom += this->ah_)
    {
      EXPECT_THAT(xt::view(src, bottom, xt::all()), ::testing::Each(NanSensitiveFloatEq(this->nan)));
      EXPECT_THAT(xt::view(src, top, xt::all()), ::testing::Each(NanSensitiveFloatEq(this->nan)));
    }

    for (size_t left = 0, right = this->aw_ - 1; right < this->mw_; left += this->aw_, right += this->aw_)
    {
      EXPECT_THAT(xt::view(src, xt::all(), left), ::testing::Each(NanSensitiveFloatEq(this->nan)));
      EXPECT_THAT(xt::view(src, xt::all(), right), ::testing::Each(NanSensitiveFloatEq(this->nan)));
    }
  }
}

TYPED_TEST(Geometry, testMaskModuleArray)
{
  using GeometryType = typename TestFixture::GeometryType;

  xt::xtensor<float, 3> src_w{xt::ones<float>({this->np_, size_t(3), size_t(4)})};
  EXPECT_THROW(GeometryType::maskModule(src_w), std::invalid_argument);

  xt::xtensor<float, 3> src{xt::ones<float>({this->np_, this->mh_, this->mw_})};
  GeometryType::maskModule(src);

  if (std::is_same<GeometryType, DetectorGeometry<EPix100>>::value)
  {
    EXPECT_THAT(xt::view(src, xt::all(), 0, xt::all()), ::testing::Each(NanSensitiveFloatEq(this->nan)));
    EXPECT_THAT(xt::view(src, xt::all(), this->mh_ - 1, xt::all()), ::testing::Each(NanSensitiveFloatEq(this->nan)));
  } else
  {
    for (size_t bottom = 0, top = this->ah_ - 1; bottom < this->mh_; top += this->ah_, bottom += this->ah_)
      {
        EXPECT_THAT(xt::view(src, xt::all(), bottom, xt::all()), ::testing::Each(NanSensitiveFloatEq(this->nan)));
        EXPECT_THAT(xt::view(src, xt::all(), top, xt::all()), ::testing::Each(NanSensitiveFloatEq(this->nan)));
      }
    for (size_t left = 0, right = this->aw_ - 1; right < this->mw_; left += this->aw_, right += this->aw_)
    {
      EXPECT_THAT(xt::view(src, xt::all(), xt::all(), left), ::testing::Each(NanSensitiveFloatEq(this->nan)));
      EXPECT_THAT(xt::view(src, xt::all(), xt::all(), right), ::testing::Each(NanSensitiveFloatEq(this->nan)));
    }
  }
}

TYPED_TEST(Geometry, testDismanleShapeCheck)
{
  // src and dst have different memory cells
  xt::xtensor<float, 3> src1 {
    xt::ones<float>({this->np_, this->shape[0], this->shape[1]}) };
  xt::xtensor<float, 4> dst1 { xt::empty<float>({this->np_ - 1, this->nm_, this->mh_, this->mw_}) };
  EXPECT_THROW(this->geom_->dismantleAllModules(src1, dst1), std::invalid_argument);

  // src has incorrect shape
  xt::xtensor<float, 4> dst2 { xt::empty<float>({this->np_, this->nm_, this->mh_, this->mw_}) };

  xt::xtensor<float, 3> src2_1 { xt::ones<float>({this->np_, this->shape[0] + 1, this->shape[1]}) };
  EXPECT_THROW(this->geom_->dismantleAllModules(src2_1, dst2), std::invalid_argument);
  xt::xtensor<float, 3> src2_2 { xt::ones<float>({this->np_, this->shape[0], this->shape[1] + 1}) };
  EXPECT_THROW(this->geom_->dismantleAllModules(src2_2, dst2), std::invalid_argument);

  // dst has incorrect shape
  xt::xtensor<float, 3> src3 { xt::ones<float>({size_t(2), this->shape[0], this->shape[1]}) };
  xt::xtensor<float, 4> dst3_1 { xt::empty<float>({size_t(2), this->nm_ + 1, this->mh_, this->mw_}) };
  EXPECT_THROW(this->geom_->dismantleAllModules(src3, dst3_1), std::invalid_argument);
  xt::xtensor<float, 4> dst3_2 { xt::empty<float>({size_t(2), this->nm_, this->mh_ + 1, this->mw_}) };
  EXPECT_THROW(this->geom_->dismantleAllModules(src3, dst3_2), std::invalid_argument);
  xt::xtensor<float, 4> dst3_3 { xt::empty<float>({size_t(2), this->nm_, this->mh_, this->mw_ + 1}) };
  EXPECT_THROW(this->geom_->dismantleAllModules(src3, dst3_3), std::invalid_argument);
}

TYPED_TEST(Geometry, testDismentalAllModulesSingle)
{
  xt::xtensor<float, 3> src { xt::ones<float>({this->nm_, this->mh_, this->mw_}) };
  xt::xtensor<float, 2> dst { xt::zeros<float>({this->shape[0], this->shape[1]}) };
  xt::xtensor<float, 3> dst_src { xt::zeros<float>(src.shape()) };

  this->geom_->positionAllModules(src, dst);
  this->geom_->dismantleAllModules(dst, dst_src); // test no throw
  EXPECT_THAT(dst_src, ::testing::Each(1.f));
}

TYPED_TEST(Geometry, testDismentalAllModules)
{
  xt::xtensor<float, 4> src { xt::ones<float>({this->np_, this->nm_, this->mh_, this->mw_}) };
  xt::xtensor<float, 3> dst { xt::zeros<float>({this->np_, this->shape[0], this->shape[1]}) };
  xt::xtensor<float, 4> dst_src { xt::zeros<float>(src.shape()) };

  this->geom_->positionAllModules(src, dst);
  this->geom_->dismantleAllModules(dst, dst_src); // test no throw
  EXPECT_THAT(dst_src, ::testing::Each(1.f));
}

} //test
} //foam